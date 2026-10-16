"""Back up a live stack and restore it into empty database and object stores.

The backup image runs its real `backup` and `restore` commands. The restored
job is read through the API's routes.
"""

from __future__ import annotations

import asyncio
import io
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import docker_lab
import httpx2
import psycopg
import pytest
from docker_lab import (
    API_TOKEN,
    BACKUP_PASSWORD,
    BUCKET,
    OFFSITE_BUCKET,
    ROLE_PASSWORD,
    S3_KEY,
    S3_SECRET,
    Lab,
    Service,
)
from fastapi import FastAPI
from rqueue import migrations

from api import migrate, queue_grants
from api import routes as routes_module
from api.core import db, repository
from api.core import settings as settings_module
from api.core import storage as storage_module
from api.core.settings import COMPUTE_QUEUE_SCHEMA
from api.core.storage import OutputStore
from api.main import app
from tsdhn.domain import CalculationResponse, EarthquakeInput, TsunamiTravelResponse
from tsdhn.engine import OutputFile, SimulationOutputs, SimulationResult
from tsdhn.runtime import RuntimeContext

pytestmark = pytest.mark.integration

docker_lab.require_docker()

# Appears only in a job's stored output, so it shows up in the backup bucket
# only if the backup leaks plaintext.
MARKER = "plaintext-marker-" + uuid.uuid4().hex
INPUT = EarthquakeInput(Mw=8.0, h=10.0, lat0=-20.5, lon0=-70.5, hhmm="0000", dia="23")


@pytest.fixture(scope="module")
def lab(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Lab]:
    laboratory = Lab()
    try:
        laboratory.setup(tmp_path_factory.mktemp("backup-context"))
        yield laboratory
    finally:
        laboratory.teardown()


async def _provision(database_url: str) -> None:
    """Apply what `compute-migrate` applies: both schemas, then the role grants."""
    with psycopg.connect(database_url) as owner:
        migrate.install_compute_schema(owner)
    connection = await asyncpg.connect(database_url)
    try:
        await migrations.migrate(connection, schema=COMPUTE_QUEUE_SCHEMA)
        async with connection.transaction():
            await queue_grants.provision_queue_roles(connection)
    finally:
        await connection.close()


@contextmanager
def _role_passwords() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as patch:
        for name in (
            "COMPUTE_PRODUCER_PASSWORD",
            "COMPUTE_WORKER_PASSWORD",
            "COMPUTE_PURGER_PASSWORD",
        ):
            patch.setattr(queue_grants, name, ROLE_PASSWORD)
        yield


def _simulation_result(directory: Path) -> SimulationResult:
    output = directory / "calculation.json"
    output.write_text(json.dumps({"marker": MARKER}), encoding="utf-8")
    return SimulationResult(
        calculation=CalculationResponse(
            length=1.0,
            width=2.0,
            dislocation=3.0,
            seismic_moment=4.0,
            tsunami_warning="none",
            distance_to_coast=5.0,
            azimuth=6.0,
            dip=7.0,
            epicenter_location="0.00/0.00",
            rectangle_parameters={},
            rectangle_corners=[],
        ),
        travel_times=TsunamiTravelResponse(
            arrival_times={"PORT": "01:00"},
            distances={"PORT": 100.0},
            epicenter_info={"lat": "0.0"},
        ),
        runtime=RuntimeContext(
            model_dir=directory, model_version="test", capabilities={}
        ),
        outputs=SimulationOutputs(
            root=directory,
            files=(OutputFile("calculation", output, "application/json"),),
        ),
    )


def _store(service: Service) -> OutputStore:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(storage_module, "S3_ENDPOINT", service.local)
        patch.setattr(storage_module, "S3_ACCESS_KEY", S3_KEY)
        patch.setattr(storage_module, "S3_SECRET_KEY", S3_SECRET)
        patch.setattr(storage_module, "S3_BUCKET", BUCKET)
        return OutputStore()


async def _finish_a_job(database_url: str, store: OutputStore, directory: Path) -> str:
    """Run a job through the repository the way a worker does, and return its id."""
    simulation_id = str(uuid.uuid4())
    deferred: list[uuid.UUID] = []

    async def defer(_connection: object, job_id: uuid.UUID) -> None:
        deferred.append(job_id)

    await db.open_pool(min_size=1, max_size=2, dsn=database_url)
    try:
        await repository.create_or_get_job(
            data=INPUT, simulation_id=simulation_id, defer=defer
        )
        async with db.acquire() as connection:
            await repository.mark_started(
                connection, deferred[0], uuid.UUID(simulation_id), 1
            )
            row = await repository.fetch_by_id(connection, deferred[0])
            assert row is not None
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(repository, "output_store", store)
                completed = await repository.complete_job(
                    connection, row, _simulation_result(directory), 1
                )
            assert completed
    finally:
        await db.close_pool()
    return simulation_id


@dataclass(frozen=True)
class Site:
    database: Service
    objects: Service


@pytest.fixture(scope="module")
def source(lab: Lab, tmp_path_factory: pytest.TempPathFactory) -> tuple[Site, str]:
    site = Site(lab.postgres("source-db"), lab.storage("source-s3"))
    database_url = lab.database_url(site.database)
    with _role_passwords():
        asyncio.run(_provision(database_url))
    simulation_id = asyncio.run(
        _finish_a_job(
            database_url,
            _store(site.objects),
            tmp_path_factory.mktemp("outputs"),
        )
    )
    return site, simulation_id


@pytest.fixture(scope="module")
def offsite(lab: Lab) -> Service:
    """The backup bucket. An operator creates it.

    The backup only fills it.
    """
    service = lab.storage("offsite-s3")
    lab.client(service).make_bucket(OFFSITE_BUCKET)
    return service


@pytest.fixture(scope="module")
def backed_up(lab: Lab, source: tuple[Site, str], offsite: Service) -> Service:
    site, _simulation_id = source
    result = lab.run_backup_image(
        ["backup"], database=site.database, objects=site.objects, offsite=offsite
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return offsite


def _snapshots(lab: Lab, source: Site, offsite: Service, *, password: str) -> object:
    result = lab.run_backup_image(
        ["snapshots", "--json"],
        database=source.database,
        objects=source.objects,
        offsite=offsite,
        password=password,
        entrypoint="restic",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_backup_leaves_one_snapshot_in_the_offsite_bucket(
    lab: Lab, source: tuple[Site, str], backed_up: Service
) -> None:
    snapshots = _snapshots(lab, source[0], backed_up, password=BACKUP_PASSWORD)

    assert isinstance(snapshots, list)
    assert [snapshot["hostname"] for snapshot in snapshots] == ["tsdhn"]
    assert snapshots[0]["tags"] == ["tsdhn"]


def test_the_offsite_bucket_holds_no_plaintext_and_needs_the_password(
    lab: Lab, source: tuple[Site, str], backed_up: Service
) -> None:
    client = lab.client(backed_up)
    stored = [
        client.get_object(OFFSITE_BUCKET, item.object_name or "").read()
        for item in client.list_objects(OFFSITE_BUCKET, recursive=True)
    ]
    assert stored, "the backup wrote nothing"
    assert not any(MARKER.encode() in blob for blob in stored)
    assert not any(b"compute" in blob and b"PGDMP" in blob for blob in stored)

    wrong = lab.run_backup_image(
        ["backup"],
        database=source[0].database,
        objects=source[0].objects,
        offsite=backed_up,
        password="not-the-password",
    )
    assert wrong.returncode != 0
    assert b"wrong password" in wrong.stdout + wrong.stderr


def test_a_second_backup_adds_a_snapshot_instead_of_a_repository(
    lab: Lab, source: tuple[Site, str], backed_up: Service
) -> None:
    site, _simulation_id = source
    before = _snapshots(lab, site, backed_up, password=BACKUP_PASSWORD)
    assert isinstance(before, list)

    again = lab.run_backup_image(
        ["backup"], database=site.database, objects=site.objects, offsite=backed_up
    )
    assert again.returncode == 0, again.stdout + again.stderr

    after = _snapshots(lab, site, backed_up, password=BACKUP_PASSWORD)
    assert isinstance(after, list)
    assert len(after) == len(before) + 1


@asynccontextmanager
async def _api_client(
    database_url: str, store: OutputStore
) -> AsyncIterator[httpx2.AsyncClient]:
    """The real routes over the restored database, connected as the producer role."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("COMPUTE_API_TOKEN", API_TOKEN)
        patch.setattr(settings_module, "COMPUTE_DATABASE_URL", database_url)
        patch.setattr(routes_module, "output_store", store)
        await db.open_pool(
            min_size=1,
            max_size=2,
            dsn=db.runtime_dsn(
                settings_module.COMPUTE_PRODUCER_ROLE,
                ROLE_PASSWORD,
            ),
        )
        try:
            api: FastAPI = app
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=api),
                base_url="http://api.test",
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            ) as client:
                yield client
        finally:
            await db.close_pool()


@pytest.fixture(scope="module")
def restored(lab: Lab, source: tuple[Site, str], backed_up: Service) -> Site:
    site = Site(lab.postgres("target-db"), lab.storage("target-s3"))
    result = lab.run_backup_image(
        ["restore"], database=site.database, objects=site.objects, offsite=backed_up
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with _role_passwords():
        asyncio.run(_provision(lab.database_url(site.database)))
    return site


@pytest.mark.asyncio
async def test_a_restored_job_is_readable_through_the_api(
    lab: Lab, source: tuple[Site, str], restored: Site
) -> None:
    _site, simulation_id = source

    with _role_passwords():
        async with _api_client(
            lab.database_url(restored.database), _store(restored.objects)
        ) as client:
            job = (await client.get(f"/api/v1/jobs/{simulation_id}")).json()
            outputs = (await client.get(f"/api/v1/jobs/{simulation_id}/outputs")).json()
            download = await client.get(
                f"/api/v1/jobs/{simulation_id}/outputs/calculation"
            )
            assert download.status_code == 307
        async with httpx2.AsyncClient() as storage_client:
            fetched = await storage_client.get(download.headers["location"])

    assert job["status"] == "completed"
    assert job["outputs"] == ["calculation"]
    assert job["travel_times"]["arrival_times"] == {"PORT": "01:00"}
    assert [output["name"] for output in outputs["outputs"]] == ["calculation"]
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "application/json"
    assert json.loads(fetched.content) == {"marker": MARKER}


def test_restore_refuses_a_database_that_already_has_jobs(
    lab: Lab, source: tuple[Site, str], backed_up: Service
) -> None:
    site, _simulation_id = source

    result = lab.run_backup_image(
        ["restore"], database=site.database, objects=site.objects, offsite=backed_up
    )

    assert result.returncode == 1
    assert b"refusing to restore" in result.stdout + result.stderr


def test_a_backup_that_cannot_list_the_object_store_fails_and_keeps_the_last_files(
    lab: Lab, source: tuple[Site, str], backed_up: Service
) -> None:
    site, _simulation_id = source
    before = _snapshots(lab, site, backed_up, password=BACKUP_PASSWORD)
    assert isinstance(before, list)

    result = lab.run_backup_image(
        ["backup"],
        database=site.database,
        objects=site.objects,
        offsite=backed_up,
        overrides={"TSDHN_S3_SECRET_KEY": "not-the-secret"},
    )

    assert result.returncode != 0
    assert b"backup finished" not in result.stdout + result.stderr
    after = _snapshots(lab, site, backed_up, password=BACKUP_PASSWORD)
    assert after == before


def test_a_backup_fails_and_keeps_the_last_files_when_the_bucket_is_gone(
    lab: Lab, source: tuple[Site, str], backed_up: Service
) -> None:
    site, _simulation_id = source
    before = _snapshots(lab, site, backed_up, password=BACKUP_PASSWORD)
    deleted = Site(lab.postgres("deleted-db"), lab.storage("deleted-s3"))
    client = lab.client(deleted.objects)
    client.make_bucket(BUCKET)
    client.remove_bucket(BUCKET)

    result = lab.run_backup_image(
        ["backup"],
        database=deleted.database,
        objects=deleted.objects,
        offsite=backed_up,
    )

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert b"is not in the object store" in output
    assert b"backup finished" not in output
    assert _snapshots(lab, site, backed_up, password=BACKUP_PASSWORD) == before


def test_restore_refuses_a_bucket_that_already_holds_objects(
    lab: Lab, source: tuple[Site, str], backed_up: Service
) -> None:
    target = Site(lab.postgres("busy-db"), lab.storage("busy-s3"))
    client = lab.client(target.objects)
    client.make_bucket(BUCKET)
    client.put_object(BUCKET, "unrelated/keep.txt", io.BytesIO(b"mine"), 4)

    refused = lab.run_backup_image(
        ["restore"], database=target.database, objects=target.objects, offsite=backed_up
    )

    assert refused.returncode == 1
    assert b"--wipe-objects" in refused.stdout + refused.stderr
    assert [o.object_name for o in client.list_objects(BUCKET, recursive=True)] == [
        "unrelated/keep.txt"
    ]
    with psycopg.connect(lab.database_url(target.database)) as connection:
        schemas = connection.execute(
            "SELECT count(*) FROM pg_namespace WHERE nspname = 'compute'"
        ).fetchone()
    assert schemas == (0,)

    wiped = lab.run_backup_image(
        ["restore", "--wipe-objects"],
        database=target.database,
        objects=target.objects,
        offsite=backed_up,
    )

    assert wiped.returncode == 0, wiped.stdout + wiped.stderr
    names = [o.object_name for o in client.list_objects(BUCKET, recursive=True)]
    assert "unrelated/keep.txt" not in names
    assert any(name and name.endswith("/outputs/calculation.json") for name in names)
