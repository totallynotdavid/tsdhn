import uuid

import pytest
from rqueue import Queue

from api.core import db, repository
from api.core.settings import COMPUTE_QUEUE_SCHEMA
from api.core.tasks import enqueue_simulation
from tsdhn.domain import EarthquakeInput

pytestmark = pytest.mark.integration

INPUT = EarthquakeInput(Mw=8.0, h=10.0, lat0=-20.5, lon0=-70.5, hhmm="0000", dia="23")


async def _age(queue: Queue) -> float:
    return await repository.oldest_queued_age_seconds(
        queue_schema=queue.schema, queue_name=queue.name
    )


async def _submit_waiting_for(queue: Queue, seconds: int) -> None:
    await repository.create_or_get_job(
        data=INPUT, simulation_id=str(uuid.uuid4()), defer=enqueue_simulation
    )
    async with db.acquire() as conn:
        await conn.execute(
            f"UPDATE {COMPUTE_QUEUE_SCHEMA}.jobs "  # noqa: S608
            "SET scheduled_at = now() - make_interval(secs => $1) "
            "WHERE id = (SELECT id FROM "
            f"{COMPUTE_QUEUE_SCHEMA}.jobs ORDER BY seq DESC LIMIT 1)",
            float(seconds),
        )


@pytest.mark.asyncio
async def test_an_empty_queue_has_no_age(queue: Queue) -> None:
    assert await _age(queue) == 0.0


@pytest.mark.asyncio
async def test_the_age_is_that_of_the_longest_waiting_job(queue: Queue) -> None:
    await _submit_waiting_for(queue, 30)
    await _submit_waiting_for(queue, 300)
    await _submit_waiting_for(queue, 60)

    assert 300 <= await _age(queue) < 310


@pytest.mark.asyncio
async def test_a_job_waiting_out_a_retry_delay_is_not_queued(queue: Queue) -> None:
    await _submit_waiting_for(queue, -600)

    assert await _age(queue) == 0.0


@pytest.mark.asyncio
async def test_a_leased_job_is_not_queued(queue: Queue) -> None:
    await _submit_waiting_for(queue, 120)
    async with db.acquire() as conn:
        await conn.execute(
            f"UPDATE {COMPUTE_QUEUE_SCHEMA}.jobs SET state = 'leased', "  # noqa: S608
            "lease_token = gen_random_uuid(), leased_until = now() + interval '1 min'"
        )

    assert await _age(queue) == 0.0
