"""Read and write the compute service's job state.

JSON columns are written as `$n::text::jsonb` and read back with an explicit
`::text` cast, then decoded with `json.loads`. asyncpg has no `Jsonb` wrapper,
and whether a connection carries a jsonb codec depends on who configured it.
Casting on both sides behaves the same either way.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, cast

import anyio
import asyncpg

from api.core.db import JobRow, acquire, notify_channel, transient_connection_errors
from api.core.storage import iso, output_store
from tsdhn.domain import EarthquakeInput, JobStatus
from tsdhn.engine import SimulationResult
from tsdhn.utils.file_utils import sanitize_for_log

__all__ = [
    "StoredOutput",
    "complete_job",
    "create_or_get_job",
    "fetch_by_id",
    "get_current_step",
    "get_job_status",
    "get_outputs",
    "is_database_connected",
    "list_abandoned_work_dirs",
    "mark_started",
    "reconcile_terminal_jobs",
    "record_failure",
    "record_progress",
]

logger = logging.getLogger(__name__)

StoredOutput = dict[str, str]

# These details are safe to show to researchers.
FAILED_JOB_DETAILS = "Pipeline failed - check error logs"
RECONCILED_JOB_DETAILS = "Failed - reconciled from the task queue"

# The queue's `error_type` is an exception class name, the same shape
# `_public_error` exposes, so it is safe to show. The message states that no
# run reported this outcome.
RECONCILED_ERROR = (
    "Simulation stopped without reporting a result; "
    "status reconciled from the task queue (%s)"
)

# Queue states in which the queue gave up on the job. `succeeded` is excluded.
# The queue records it only after `run_simulation_task` returned, which happens
# only after `complete_job` committed compute.jobs.
QUEUE_GAVE_UP = ("failed", "cancelled")

# A job that reported its own outcome is never overwritten, by anyone.
TERMINAL_STATUSES = [JobStatus.COMPLETED.value, JobStatus.FAILED.value]

# The canonical form `str(uuid.UUID(...))` produces, and the only form
# `enqueue_simulation` writes. Reconciliation skips any other form instead of
# casting it. See `_reconcile_sql`.
CANONICAL_UUID_RE = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

# The jsonb columns come back as text and are decoded below.
_JSON_COLUMNS = ("input_params", "calculation", "travel_times", "outputs")

_COLUMNS = """
  id, simulation_id, status, input_params::text AS input_params, details, step,
  step_index, total_steps, calculation::text AS calculation,
  travel_times::text AS travel_times, outputs::text AS outputs, error,
  created_at, updated_at, started_at, finished_at
"""


def _sql(template: str) -> str:
    return template.format(columns=_COLUMNS)


SELECT_BY_SIMULATION_ID = _sql(
    "SELECT {columns} FROM compute.jobs WHERE simulation_id = $1"
)
SELECT_BY_ID = _sql("SELECT {columns} FROM compute.jobs WHERE id = $1")

INSERT_JOB_SQL = _sql(
    """
    INSERT INTO compute.jobs (id, simulation_id, status, input_params, details)
    VALUES ($1, $2, $3, $4::text::jsonb, $5)
    ON CONFLICT (simulation_id) DO NOTHING
    RETURNING {columns}
    """
)


def as_uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value, version=4)


def _model_dump(data: EarthquakeInput) -> dict[str, Any]:
    dumped: object = data.model_dump(mode="json")
    if not isinstance(dumped, dict):
        raise TypeError("EarthquakeInput did not dump to a JSON object")
    return cast(dict[str, Any], dumped)


def _decode(record: asyncpg.Record | None) -> JobRow | None:
    """Turn one selected row into a plain mapping with JSON already parsed."""
    if record is None:
        return None
    row: JobRow = dict(record)
    for column in _JSON_COLUMNS:
        encoded = row.get(column)
        if isinstance(encoded, str):
            row[column] = json.loads(encoded)
    return row


async def _notify(conn: asyncpg.Connection, simulation_id: uuid.UUID) -> None:
    """Notify listeners of `simulation_id`. Delivery waits for the commit."""
    await conn.execute(f"NOTIFY {notify_channel(simulation_id)}")


def status_from_row(row: JobRow) -> dict[str, Any]:
    status = str(row["status"])
    outputs = row["outputs"] or []
    return {
        "status": status,
        "details": row["details"],
        "step": row["step"],
        "step_index": row["step_index"],
        "total_steps": row["total_steps"],
        "calculation": row["calculation"],
        "travel_times": row["travel_times"],
        "error": row["error"],
        "created_at": iso(row["created_at"]),
        "started_at": iso(row["started_at"]),
        "finished_at": iso(row["finished_at"]),
        "outputs": [output["name"] for output in outputs],
    }


def _public_error(e: Exception, step: str | None) -> str:
    """The user-facing error stored in compute.jobs.error.

    Raw exception messages embed server filesystem paths (jobs dir, model
    locations), so only the exception class and failed step are exposed;
    the full traceback stays in the worker logs.
    """
    if step:
        return f"Simulation failed at step '{step}' ({type(e).__name__})"
    return f"Simulation failed ({type(e).__name__})"


async def fetch_by_id(conn: asyncpg.Connection, job_id: uuid.UUID) -> JobRow | None:
    async with transient_connection_errors(conn):
        return _decode(await conn.fetchrow(SELECT_BY_ID, job_id))


async def create_or_get_job(
    *, data: EarthquakeInput, simulation_id: str, defer: Any
) -> dict[str, Any]:
    """Insert a job and enqueue it in one transaction.

    `defer` is awaited with the open connection and the new compute job id,
    which keeps this module independent of the queue implementation. Raises
    `ValueError` when the simulation id exists with different input. Returns
    the existing job's status when the input matches.
    """
    simulation_uuid = as_uuid(simulation_id)
    input_params = _model_dump(data)

    async with acquire() as conn, conn.transaction():
        compute_job_id = uuid.uuid4()
        inserted = _decode(
            await conn.fetchrow(
                INSERT_JOB_SQL,
                compute_job_id,
                simulation_uuid,
                JobStatus.QUEUED.value,
                json.dumps(input_params),
                "Queued for simulation worker",
            )
        )

        if inserted is None:
            existing = _decode(
                await conn.fetchrow(SELECT_BY_SIMULATION_ID, simulation_uuid)
            )
            if existing is None:
                raise RuntimeError("Compute job was not persisted")
            if existing["input_params"] != input_params:
                raise ValueError("Job id already exists with different input")
            return status_from_row(existing)

        await defer(conn, compute_job_id)
        return status_from_row(inserted)


async def get_job_status(simulation_id: str) -> dict[str, Any]:
    try:
        simulation_uuid = as_uuid(simulation_id)
        async with acquire() as conn:
            row = _decode(await conn.fetchrow(SELECT_BY_SIMULATION_ID, simulation_uuid))
    except Exception as e:
        logger.error("Job lookup failed for %s: %s", sanitize_for_log(simulation_id), e)
        raise ValueError("Invalid or unknown job ID") from e

    if row is None:
        raise ValueError("Invalid or unknown job ID")
    return status_from_row(row)


async def get_outputs(simulation_id: str) -> list[StoredOutput]:
    """Return the outputs recorded with a completed job."""
    simulation_uuid = as_uuid(simulation_id)
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT status, outputs::text AS outputs FROM compute.jobs
            WHERE simulation_id = $1
            """,
            simulation_uuid,
        )
    if row is None:
        raise ValueError("Invalid or unknown job ID")
    if row["status"] != JobStatus.COMPLETED.value:
        return []
    # `outputs` is NOT NULL today. This query bypasses `_decode` and reads the
    # column as text, so a relaxed constraint would make `json.loads(None)`
    # raise.
    encoded = row["outputs"]
    if encoded is None:
        return []
    return cast(list[StoredOutput], json.loads(encoded) or [])


async def get_current_step(conn: asyncpg.Connection, job_uuid: uuid.UUID) -> str | None:
    async with transient_connection_errors(conn):
        row = await conn.fetchrow(
            "SELECT step FROM compute.jobs WHERE id = $1", job_uuid
        )
    return str(row["step"]) if row and row["step"] else None


async def list_abandoned_work_dirs(cutoff: datetime) -> list[str]:
    """Return terminal job workspaces older than the retention cutoff."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT simulation_id FROM compute.jobs
            WHERE status = ANY($1::text[])
              AND finished_at IS NOT NULL AND finished_at < $2
            """,
            [JobStatus.FAILED.value, JobStatus.COMPLETED.value],
            cutoff,
        )
    return [str(row["simulation_id"]) for row in rows]


def _reconcile_sql(queue_schema: str) -> str:
    """Build the reconciliation statement for one queue schema.

    `queue_schema` is interpolated because PostgreSQL has no bind parameter for
    an identifier. Its only source is `rqueue.Queue.schema`, which rqueue
    validated when the queue was built.
    """
    # Casting `payload->>'compute_job_id'` to uuid aborts the whole statement on
    # one malformed value, which would leave every other stuck job unreconciled.
    # The regex and the cast cannot share a WHERE clause because PostgreSQL may
    # evaluate the qualifiers in either order. The cast is in the select list of
    # a MATERIALIZED CTE, behind the regex in that CTE's WHERE, so it runs only
    # for rows that passed the filter. A payload this codebase did not write is
    # skipped.
    #
    # `gave_up` is read once at statement start. The UPDATE can then block on a
    # concurrent `mark_started`, and in that window an operator retry can requeue
    # the job and a new attempt can take ownership of the compute row.
    # `j.owner_attempt <= q.attempt` skips that row. PostgreSQL re-evaluates an
    # UPDATE's qualifiers against the latest committed row version when it
    # unblocks (READ COMMITTED), so `j.owner_attempt` is the value the
    # concurrent claim committed. Without the predicate the pass would fail a
    # running job that a live attempt rightfully owns, and that attempt's
    # `complete_job` would then be refused by the terminal-status guard.
    #
    # If the pass takes the row lock first, it marks the row failed at the older
    # attempt and the live attempt's `mark_started` reclaims it as strictly
    # newer. Neither order needs a lock on rqueue's tables.
    #
    # `owner_attempt` never exceeds the queue's attempt counter. It is written
    # only from `context.attempt` or by this pass from `q.attempt`, so once a
    # queue row settles at its final attempt a later pass always matches.
    #
    # `GREATEST(COALESCE(...))` keeps the stamp from moving backwards. The two
    # counters can disagree: a job cancelled before its first lease has queue
    # attempt 0 and a NULL `owner_attempt`.
    return f"""
        WITH gave_up AS MATERIALIZED (
            SELECT (payload->>'compute_job_id')::uuid AS compute_job_id,
                   state, error_type, finished_at, attempt
            FROM {queue_schema}.jobs
            WHERE queue = $4
              AND task = $5
              AND state = ANY($6::text[])
              AND finished_at < $7
              AND payload->>'compute_job_id' ~* $9
        )
        UPDATE compute.jobs AS j
        SET status = $1,
            details = $2,
            error = format($3::text, COALESCE(q.error_type, q.state)),
            finished_at = COALESCE(j.finished_at, q.finished_at, now()),
            owner_attempt = GREATEST(COALESCE(j.owner_attempt, 0), q.attempt),
            updated_at = now()
        FROM gave_up AS q
        WHERE j.id = q.compute_job_id
          AND j.status <> ALL($8::text[])
          AND (j.owner_attempt IS NULL OR j.owner_attempt <= q.attempt)
        RETURNING j.id, j.simulation_id
    """  # noqa: S608


async def reconcile_terminal_jobs(
    *, queue_schema: str, queue_name: str, task: str, cutoff: datetime
) -> list[uuid.UUID]:
    """Fail compute jobs the queue gave up on, and return their ids.

    A run normally writes its own outcome with `record_failure` or
    `complete_job`. Some paths end a job without that write: rqueue failing a
    job whose lease expired on its last attempt without calling the handler, a
    failure inside `complete_job` after the kernel finished, and an outage that
    also defeats `record_failure`. In each the queue row is terminal while
    compute.jobs is still unfinished.

    Only rows the queue gave up on and compute.jobs has not finished are
    touched. Repeating the pass, or running it on two workers at once, changes
    nothing the first pass did not, because the guard is evaluated under the
    row lock the UPDATE takes.

    The pass stamps `owner_attempt` with the queue's attempt. `mark_started`
    lets only a strictly newer attempt reclaim a failed row, so a wedged
    attempt that wakes up later cannot reopen the row while an operator retry
    can.
    """
    async with acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            _reconcile_sql(queue_schema),
            JobStatus.FAILED.value,
            RECONCILED_JOB_DETAILS,
            RECONCILED_ERROR,
            queue_name,
            task,
            list(QUEUE_GAVE_UP),
            cutoff,
            TERMINAL_STATUSES,
            CANONICAL_UUID_RE,
        )
        # Same transaction as the update, so a watching SSE stream wakes only
        # for a state that has committed.
        for row in rows:
            await _notify(conn, row["simulation_id"])
    return [row["id"] for row in rows]


async def is_database_connected() -> bool:
    try:
        async with acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


async def mark_started(
    conn: asyncpg.Connection,
    job_uuid: uuid.UUID,
    simulation_id: uuid.UUID,
    attempt: int,
) -> bool:
    """Claim this row for `attempt` and return whether the claim was won.

    One statement takes ownership, refuses to reopen a finished job, and marks
    the job running. The claim is lost when a newer attempt owns the row or the
    job is `completed`. Delivery is at least once, so a completed job can come
    back, and re-running it would flip a finished row to `running` for every
    watcher.

    A `failed` row is refused only to an attempt that is not strictly newer
    than the row's owner, because two paths lead there and need opposite
    answers:

    - An operator restarts a failed job with `rqueue.Admin.retry_job`, which
      requeues the same row. The retry must be able to reclaim the failed
      compute row, or the whole simulation would run with every write rejected.
    - `reconcile_terminal_jobs` fails a row for a queue that gave up and stamps
      the attempt it failed. That attempt, a worker wedged past its lease, may
      wake up and reach here. Reopening the row would leave compute.jobs
      `running` under a queue row that says `failed`.

    Strict inequality separates them because rqueue's attempt counter only
    increases. `storage.lease_jobs` increments it on every claim, and
    `Admin.retry_job` raises `max_attempts` instead of resetting it.

    A reclaimed row has the previous attempt's `error` and `finished_at`
    cleared, because `status_from_row` returns both to clients beside the new
    `running`.
    """
    # asyncpg commits each statement on its own. The transaction keeps the
    # NOTIFY with its UPDATE, so no client is woken to read an uncommitted
    # state.
    async with transient_connection_errors(conn), conn.transaction():
        claimed = await conn.fetchval(
            """
            UPDATE compute.jobs
            SET status = $1, details = $2, owner_attempt = $3,
                error = NULL, finished_at = NULL,
                started_at = COALESCE(started_at, now()), updated_at = now()
            WHERE id = $4
              AND (owner_attempt IS NULL OR owner_attempt <= $3)
              AND status <> $5
              AND (status <> $6 OR owner_attempt IS NULL OR owner_attempt < $3)
            RETURNING id
            """,
            JobStatus.RUNNING.value,
            "Simulation worker started",
            attempt,
            job_uuid,
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
        )
        if claimed is None:
            return False
        await _notify(conn, simulation_id)
    return True


async def record_progress(
    conn: asyncpg.Connection,
    job_uuid: uuid.UUID,
    simulation_id: uuid.UUID,
    message: str,
    details: dict[str, Any],
    attempt: int,
) -> bool:
    """Write one progress update fenced on owning the attempt.

    Returns whether the write landed. The kernel thread makes this write, and
    it can outlive its coroutine (see `api.core.tasks`). Two predicates in the
    same statement make that safe:

    - `owner_attempt = $9` refuses a superseded attempt.
    - `status <> ALL(TERMINAL_STATUSES)` refuses a finished job. An attempt
      that reconciliation failed is still the owner, so the attempt fence alone
      would let its stale write flip `failed` back to `running`.

    A refused write is normal, not an error.
    """
    calculation = details.get("calculation")
    travel_times = details.get("travel_times")
    async with transient_connection_errors(conn), conn.transaction():
        written = await conn.fetchval(
            """
            UPDATE compute.jobs
            SET status = $1,
                details = $2,
                step = COALESCE($3::text, step),
                step_index = COALESCE($4::integer, step_index),
                total_steps = COALESCE($5::integer, total_steps),
                calculation = COALESCE($6::text::jsonb, calculation),
                travel_times = COALESCE($7::text::jsonb, travel_times),
                updated_at = now()
            WHERE id = $8
              AND owner_attempt = $9
              AND status <> ALL($10::text[])
            RETURNING id
            """,
            JobStatus.RUNNING.value,
            message,
            details.get("step"),
            details.get("step_index"),
            details.get("total_steps"),
            json.dumps(calculation) if "calculation" in details else None,
            json.dumps(travel_times) if "travel_times" in details else None,
            job_uuid,
            attempt,
            TERMINAL_STATUSES,
        )
        if written is None:
            return False
        await _notify(conn, simulation_id)
    return True


async def record_failure(
    conn: asyncpg.Connection,
    job_uuid: uuid.UUID,
    simulation_id: uuid.UUID,
    exc: Exception,
    *,
    step: str | None,
    will_retry: bool,
    attempt: int,
) -> None:
    """Record a failed run.

    When the exception will be retried this only updates `details` and leaves
    the status `running`, so an in-flight retry does not look terminal.

    Both statements carry the `owner_attempt` fence and skip a terminal row.
    The terminal guard matters because `complete_job` can fail after its UPDATE
    committed, since a connection lost at commit is ambiguous. The caller then
    reports a failure for a job that is finished.
    """
    logger.exception("Simulation failed for compute job %s", job_uuid)
    async with transient_connection_errors(conn), conn.transaction():
        if will_retry:
            await conn.execute(
                "UPDATE compute.jobs SET details = $1, updated_at = now() "
                "WHERE id = $2 AND owner_attempt = $3 "
                "AND status <> ALL($4::text[])",
                f"Retrying after transient error ({type(exc).__name__})",
                job_uuid,
                attempt,
                TERMINAL_STATUSES,
            )
        else:
            await conn.execute(
                """
                UPDATE compute.jobs
                SET status = $1, details = $2, error = $3,
                    finished_at = now(), updated_at = now()
                WHERE id = $4 AND owner_attempt = $5
                  AND status <> ALL($6::text[])
                """,
                JobStatus.FAILED.value,
                FAILED_JOB_DETAILS,
                _public_error(exc, step),
                job_uuid,
                attempt,
                TERMINAL_STATUSES,
            )
        await _notify(conn, simulation_id)


async def complete_job(
    conn: asyncpg.Connection, row: JobRow, result: SimulationResult, attempt: int
) -> bool:
    """Upload the result and commit its manifest with the terminal state.

    Returns whether the manifest landed. The upload has happened by the time
    the UPDATE runs, so a refused write leaves objects in MinIO that
    compute.jobs does not point at. The refusal is logged with the object
    location, and the caller must be able to tell.

    The UPDATE is fenced on `owner_attempt` and on the row not being terminal,
    as in `record_progress`. An attempt that reconciliation failed is still the
    owner, so without the status guard its late completion would flip the row
    to `completed` under a queue row that says `failed`.

    Refusing discards a real result. Recording it would leave the two systems
    permanently disagreeing with nothing left to reconcile them.
    """
    now = datetime.now().astimezone()
    simulation_id = str(row["simulation_id"])
    compute_job_id = str(row["id"])
    calculation = result.calculation.model_dump(mode="json")
    travel_times = result.travel_times.model_dump(mode="json")

    outputs: list[StoredOutput] = [
        {
            "name": output.name,
            "key": f"simulations/{simulation_id}/outputs/{output.path.name}",
            "filename": output.path.name,
            "content_type": output.content_type,
        }
        for output in result.outputs.files
    ]

    metadata = {
        "simulation_id": simulation_id,
        "compute_job_id": compute_job_id,
        "status": JobStatus.COMPLETED.value,
        "created_at": iso(row["created_at"]),
        "started_at": iso(row["started_at"]),
        "finished_at": now.isoformat(),
        "calculation": calculation,
        "travel_times": travel_times,
        "outputs": outputs,
    }
    # MinIO's client is blocking. Uploading on the event loop would stall every
    # other coroutine in the worker, heartbeats included.
    bucket, metadata_key = await anyio.to_thread.run_sync(
        lambda: output_store.upload_simulation_result(
            simulation_id=simulation_id,
            compute_job_id=compute_job_id,
            outputs=result.outputs,
            metadata=metadata,
        )
    )

    async with transient_connection_errors(conn), conn.transaction():
        written = await conn.fetchval(
            """
            UPDATE compute.jobs
            SET status = $1, details = $2, calculation = $3::text::jsonb,
                travel_times = $4::text::jsonb, outputs = $5::text::jsonb,
                result_bucket = $6, result_key = $7, error = NULL,
                finished_at = $8, updated_at = now()
            WHERE id = $9 AND owner_attempt = $10
              AND status <> ALL($11::text[])
            RETURNING id
            """,
            JobStatus.COMPLETED.value,
            "Simulation completed successfully",
            json.dumps(calculation),
            json.dumps(travel_times),
            json.dumps(outputs),
            bucket,
            metadata_key,
            now,
            row["id"],
            attempt,
            TERMINAL_STATUSES,
        )
        if written is None:
            logger.error(
                "Compute job %s is no longer attempt %d's to finish (a newer "
                "attempt owns it, or the queue already gave up on it and the "
                "row was reconciled); its result was "
                "uploaded to %s/%s but not recorded, and nothing in compute.jobs "
                "now points at it",
                compute_job_id,
                attempt,
                bucket,
                metadata_key,
            )
            return False
        await _notify(conn, row["simulation_id"])
    return True
