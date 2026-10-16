"""Output retention against PostgreSQL and a RustFS container."""

import io
import json
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import docker_lab
import pytest
from docker_lab import BUCKET, S3_KEY, S3_SECRET, Lab, Service
from rqueue import Queue

from api.core import db, repository, tasks
from api.core import storage as storage_module
from api.core.errors import OutputsExpiredError, TransientInfraError
from api.core.storage import OutputStore
from tsdhn.domain import EarthquakeInput

pytestmark = pytest.mark.integration

docker_lab.require_docker()

INPUT = EarthquakeInput(Mw=8.0, h=10.0, lat0=-20.5, lon0=-70.5, hhmm="0000", dia="23")
OUTPUT = {
    "name": "calculation",
    "key": "simulations/{id}/outputs/calculation.json",
    "filename": "calculation.json",
    "content_type": "application/json",
}


async def _completed_job(*, finished_days_ago: float) -> str:
    simulation_id = str(uuid.uuid4())

    async def defer(_conn: Any, _job_id: uuid.UUID) -> None:
        return None

    await repository.create_or_get_job(
        data=INPUT, simulation_id=simulation_id, defer=defer
    )
    outputs = [dict(OUTPUT, key=OUTPUT["key"].format(id=simulation_id))]
    async with db.acquire() as conn:
        await conn.execute(
            """
            UPDATE compute.jobs
            SET status = 'completed', outputs = $2::text::jsonb,
                finished_at = now() - make_interval(secs => $3)
            WHERE simulation_id = $1
            """,
            uuid.UUID(simulation_id),
            json.dumps(outputs),
            finished_days_ago * 86400,
        )
    return simulation_id


@pytest.fixture(scope="module")
def storage() -> Iterator[Service]:
    lab = Lab()
    lab.setup_network()
    try:
        service = lab.storage("results")
        lab.client(service).make_bucket(BUCKET)
        yield service
    finally:
        lab.teardown()


def _store(service: Service, *, endpoint: str | None = None) -> OutputStore:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(storage_module, "S3_ENDPOINT", endpoint or service.local)
        patch.setattr(storage_module, "S3_ACCESS_KEY", S3_KEY)
        patch.setattr(storage_module, "S3_SECRET_KEY", S3_SECRET)
        patch.setattr(storage_module, "S3_BUCKET", BUCKET)
        return OutputStore()


@pytest.fixture
def store(storage: Service, monkeypatch: pytest.MonkeyPatch) -> OutputStore:
    """The object store the expiry pass deletes from."""
    real = _store(storage)
    monkeypatch.setattr(tasks, "output_store", real)
    return real


def _put(service: Service, simulation_id: str, *names: str) -> None:
    client = Lab.client(service)
    for name in names:
        client.put_object(
            BUCKET, f"simulations/{simulation_id}/{name}", io.BytesIO(b"{}"), 2
        )


def _stored(service: Service, simulation_id: str) -> list[str]:
    listing = Lab.client(service).list_objects(
        BUCKET, prefix=f"simulations/{simulation_id}/", recursive=True
    )
    return sorted(item.object_name or "" for item in listing)


# What a finished job leaves in the bucket, including a key two levels deep.
FILES = ("metadata.json", "outputs/calculation.json", "outputs/frames/step-0001.json")


@pytest.mark.asyncio
async def test_a_pass_deletes_every_object_of_an_old_job_and_only_those(
    queue: Queue, store: OutputStore, storage: Service
) -> None:
    old = await _completed_job(finished_days_ago=100)
    recent = await _completed_job(finished_days_ago=1)
    _put(storage, old, *FILES)
    _put(storage, recent, *FILES)

    assert await tasks.expire_old_outputs(timedelta(days=90)) == 1

    assert _stored(storage, old) == []
    assert len(_stored(storage, recent)) == len(FILES)
    expired = await repository.get_job_status(old)
    assert expired["status"] == "completed"
    assert expired["outputs"] == []
    assert expired["outputs_expired_at"] is not None
    # What the user asked for and the arrival times are not outputs.
    assert expired["finished_at"] is not None
    kept = await repository.get_job_status(recent)
    assert kept["outputs"] == ["calculation"]
    assert kept["outputs_expired_at"] is None


@pytest.mark.asyncio
async def test_outputs_of_an_expired_job_are_gone_not_empty(
    queue: Queue, store: OutputStore, storage: Service
) -> None:
    simulation_id = await _completed_job(finished_days_ago=100)
    _put(storage, simulation_id, *FILES)
    await tasks.expire_old_outputs(timedelta(days=90))

    with pytest.raises(OutputsExpiredError) as expired:
        await repository.get_outputs(simulation_id)

    assert expired.value.expired_at is not None


@pytest.mark.asyncio
async def test_the_worker_creates_the_bucket_when_it_starts(
    storage: Service, store: OutputStore
) -> None:
    client = Lab.client(storage)
    for item in client.list_objects(BUCKET, recursive=True):
        client.remove_object(BUCKET, item.object_name or "")
    client.remove_bucket(BUCKET)

    await tasks.ensure_output_bucket()

    assert client.bucket_exists(BUCKET)


@pytest.mark.asyncio
async def test_a_store_that_does_not_answer_does_not_stop_the_worker(
    storage: Service, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tasks, "output_store", _store(storage, endpoint="127.0.0.1:1"))

    await tasks.ensure_output_bucket()


@pytest.mark.asyncio
async def test_a_second_pass_leaves_an_expired_job_alone(
    queue: Queue, store: OutputStore, storage: Service
) -> None:
    simulation_id = await _completed_job(finished_days_ago=100)
    _put(storage, simulation_id, *FILES)

    assert await tasks.expire_old_outputs(timedelta(days=90)) == 1
    assert await tasks.expire_old_outputs(timedelta(days=90)) == 0
    assert _stored(storage, simulation_id) == []


@pytest.mark.asyncio
async def test_a_job_whose_files_are_already_gone_still_expires(
    queue: Queue, store: OutputStore
) -> None:
    simulation_id = await _completed_job(finished_days_ago=100)

    assert await tasks.expire_old_outputs(timedelta(days=90)) == 1

    assert (await repository.get_job_status(simulation_id))["outputs"] == []


@pytest.mark.asyncio
async def test_a_pass_works_through_more_jobs_than_one_batch(
    queue: Queue, store: OutputStore, storage: Service
) -> None:
    ids = [await _completed_job(finished_days_ago=100) for _ in range(5)]
    for simulation_id in ids:
        _put(storage, simulation_id, *FILES)

    assert await tasks.expire_old_outputs(timedelta(days=90), batch=2) == 5
    assert [_stored(storage, simulation_id) for simulation_id in ids] == [[]] * 5


@pytest.mark.asyncio
async def test_a_storage_failure_keeps_the_files_listed_for_the_next_pass(
    queue: Queue, storage: Service, monkeypatch: pytest.MonkeyPatch
) -> None:
    simulation_id = await _completed_job(finished_days_ago=100)
    # Nothing listens on port 1.
    monkeypatch.setattr(tasks, "output_store", _store(storage, endpoint="127.0.0.1:1"))

    with pytest.raises(TransientInfraError):
        await tasks.expire_old_outputs(timedelta(days=90))

    assert await repository.get_outputs(simulation_id) != []
