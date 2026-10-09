"""Queue tasks for simulation runs and worker maintenance.

The kernel thread outlives a cancelled handler, so two fences keep it from
harming the attempt that took over: `compute.jobs.owner_attempt` in the
database and an exclusive `flock` on the workspace.
"""

import asyncio
import contextlib
import fcntl
import logging
import os
import shutil
import threading
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg
from rqueue import (
    Admin,
    CancelJob,
    Job,
    PermanentFailure,
    Queue,
    RetryPolicy,
    TaskContext,
)
from rqueue.models import TERMINAL_STATES

from api.core import db, repository
from api.core.errors import TransientInfraError
from api.core.lifecycle import JOB_ID_RE, JOB_RETENTION, TERMINAL_STATUSES
from api.core.queue import get_queue
from api.core.settings import COMPUTE_QUEUE, JOBS_DIR
from tsdhn.domain import EarthquakeInput, JobStatus
from tsdhn.engine import run_simulation

__all__ = [
    "MAX_ATTEMPTS",
    "RUN_SIMULATION",
    "TRANSIENT_RETRY",
    "AbandonedAttempt",
    "decode_payload",
    "enqueue_simulation",
    "purge_finished_jobs",
    "reconcile_terminal_jobs",
    "register_tasks",
    "run_periodic_purge",
    "run_periodic_reconcile",
    "run_periodic_sweep",
    "run_simulation_task",
    "sweep_abandoned_work_dirs",
]

logger = logging.getLogger(__name__)

RUN_SIMULATION = "api.run_simulation"


class AbandonedAttempt(Exception):
    """Raised in the kernel thread when its attempt no longer owns the job."""


MAX_ATTEMPTS = 3
TRANSIENT_RETRY = RetryPolicy(
    max_attempts=MAX_ATTEMPTS,
    initial_backoff=15.0,
    multiplier=2.0,
    retry_on=(TransientInfraError,),
)

# A simulation has no meaningful upper bound. Lease recovery reclaims a run
# whose worker died.
RUN_TIMEOUT_SECONDS: float | None = None

# Beside the workspace, not inside it: a fresh run removes the whole directory.
WORKSPACE_LOCK_SUFFIX = ".lock"

WORK_DIR_TTL = timedelta(hours=24)
SWEEP_INTERVAL_SECONDS = 3600.0

# Longer than any write by a worker that lost its lease and reports after
# rqueue failed the row.
RECONCILE_GRACE = timedelta(minutes=5)
RECONCILE_INTERVAL_SECONDS = 60.0

# asyncio holds tasks weakly.
_CLAIM_DRAIN_TASKS: set[asyncio.Task[None]] = set()

PURGE_INTERVAL_SECONDS = 3600.0

# Bounds one purge pass; the next pass takes the rest.
PURGE_LIMIT = 10000


def decode_payload(payload: Any) -> uuid.UUID:
    """Turn a queued payload into the compute job id it names.

    Raises for a malformed payload. The error is not transient, so the job
    fails without retries.
    """
    if not isinstance(payload, dict):
        raise ValueError("simulation payload must be a JSON object")
    return repository.as_uuid(str(payload["compute_job_id"]))


async def enqueue_simulation(
    connection: asyncpg.Connection, compute_job_id: uuid.UUID
) -> Job:
    """Queue the task on `connection` so it commits with the job row.

    `dedupe_key` allows one queued job per compute job. `concurrency_key`
    allows one running simulation per compute job.
    """
    return await get_queue().enqueue(
        connection,
        task=RUN_SIMULATION,
        payload={"compute_job_id": str(compute_job_id)},
        dedupe_key=f"simulation:{compute_job_id}",
        on_conflict="return_existing",
        concurrency_key=f"compute-job:{compute_job_id}",
    )


class WorkspaceClaim:
    """One exclusive `flock` on a workspace, closed by whichever holder releases last.

    The kernel thread and the coroutine each hold a share and can end in either
    order.
    """

    def __init__(self, fd: int, shares: int = 2) -> None:
        self._fd = fd
        self._shares = shares
        self._guard = threading.Lock()

    def release(self) -> None:
        """Give back one share. Closing is the last releaser's job."""
        with self._guard:
            self._shares -= 1
            if self._shares > 0:
                return
            fd, self._fd = self._fd, -1
        if fd >= 0:
            os.close(fd)


def _lock_path(work_dir: Path) -> Path:
    return work_dir.with_name(work_dir.name + WORKSPACE_LOCK_SUFFIX)


def claim_workspace(work_dir: Path, attempt: int) -> tuple[WorkspaceClaim, bool]:
    """Take this attempt's exclusive claim on `work_dir` and return whether to resume.

    Raises `TransientInfraError` while another holder has the lock, so rqueue's
    backoff waits for an abandoned kernel thread to unwind.
    """
    lock_path = _lock_path(work_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            raise TransientInfraError(
                f"simulation workspace {work_dir.name} is still held by an "
                "earlier attempt"
            ) from e
        os.ftruncate(fd, 0)
        os.write(fd, f"attempt {attempt}\n".encode())
        return WorkspaceClaim(fd), work_dir.exists()
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        raise


async def _release_unreceived_claim(
    claim_future: asyncio.Future[tuple[WorkspaceClaim, bool]],
) -> None:
    """Release a claim whose thread completed after its waiter was cancelled."""
    try:
        claim, _resume = await claim_future
    except Exception, asyncio.CancelledError:
        return
    # The coroutine never received the claim, so the drain owns both shares.
    claim.release()
    claim.release()


async def _claim_workspace_safely(
    work_dir: Path, attempt: int
) -> tuple[WorkspaceClaim, bool]:
    """Claim a workspace without leaking the claim when cancelled.

    The thread cannot be stopped once it holds the lock, so it is shielded and
    a detached drain task releases the claim if cancellation wins.
    """
    claim_future = asyncio.create_task(
        asyncio.to_thread(claim_workspace, work_dir, attempt)
    )
    try:
        return await asyncio.shield(claim_future)
    except asyncio.CancelledError:
        drain = asyncio.create_task(_release_unreceived_claim(claim_future))
        _CLAIM_DRAIN_TASKS.add(drain)
        drain.add_done_callback(_CLAIM_DRAIN_TASKS.discard)
        raise


def remove_workspace(work_dir: Path) -> bool:
    """Remove a workspace and its lock unless something still holds the lock.

    The lock is taken before the unlink because unlinking a locked file lets the
    next `O_CREAT` lock a new inode without contention.

    Returns whether the workspace was removed. A refusal is not an error.
    """
    lock_path = _lock_path(work_dir)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        # No lock file exists and none can be created: nothing claimed it.
        shutil.rmtree(work_dir, ignore_errors=True)
        return True
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            logger.info(
                "Workspace %s is still held; leaving it for the next sweep",
                work_dir.name,
            )
            return False
        shutil.rmtree(work_dir, ignore_errors=True)
        with contextlib.suppress(OSError):
            lock_path.unlink()
    finally:
        os.close(fd)
    return True


async def run_simulation_task(compute_job_id: uuid.UUID, context: TaskContext) -> None:
    """Run one simulation end to end, streaming progress into compute.jobs.

    Raises `CancelJob` when this attempt no longer owns the job.
    """
    async with db.acquire() as conn:
        row = await repository.fetch_by_id(conn, compute_job_id)
    if row is None:
        # No retry can create a missing job.
        raise PermanentFailure(f"Unknown compute job {compute_job_id}")

    simulation_id: uuid.UUID = row["simulation_id"]
    work_dir = JOBS_DIR / str(simulation_id)
    data = EarthquakeInput(**row["input_params"])

    # The claim is the decision. Branching on `row["status"]` from the SELECT
    # above would leave a check-then-write gap. An attempt completing between
    # that SELECT and this UPDATE could have its `completed` overwritten with
    # `running`.
    async with db.acquire() as conn:
        claimed = await repository.mark_started(
            conn, compute_job_id, simulation_id, context.attempt
        )
    if not claimed:
        await _stand_down(compute_job_id, work_dir, context.attempt)
        return

    # Captured before the hop into the thread. The progress callback runs on
    # that thread and needs the loop that owns the pool.
    loop = asyncio.get_running_loop()
    # Set when the coroutine is cancelled while the kernel thread is still
    # running, or when a progress write is refused.
    abandoned = threading.Event()

    def on_progress(message: str, details: dict[str, Any]) -> None:
        if abandoned.is_set():
            # Raising unwinds `run_simulation`, so the thread ends at this step
            # boundary instead of computing a result nobody will read.
            raise AbandonedAttempt(
                f"attempt {context.attempt} of compute job {compute_job_id} "
                "no longer owns this job"
            )
        # Blocking on the result makes progress durable before the simulation
        # moves on. A failed write surfaces in the simulation instead of a
        # dropped background task.
        written = asyncio.run_coroutine_threadsafe(
            _write_progress(
                compute_job_id, simulation_id, message, details, context.attempt
            ),
            loop,
        ).result()
        if not written:
            # The database refused the write because this attempt no longer
            # owns the row or the row is finished. The write was fenced, so
            # nothing was corrupted. Stop as above.
            abandoned.set()
            raise AbandonedAttempt(
                f"attempt {context.attempt} of compute job {compute_job_id} "
                "no longer owns this job"
            )

    def run_kernel(claim: WorkspaceClaim, resume: bool) -> Any:
        try:
            return run_simulation(
                data, work_dir, resume=resume, on_progress=on_progress
            )
        finally:
            # Released on this thread, so the claim ends when the thread stops
            # writing and not when the coroutine stops waiting.
            claim.release()

    kernel_state_guard = threading.Lock()
    kernel_started = False
    kernel_cancelled = False

    def run_kernel_if_not_cancelled(held: WorkspaceClaim, should_resume: bool) -> Any:
        """Start the kernel only if cancellation has not claimed its share."""
        nonlocal kernel_started
        with kernel_state_guard:
            if kernel_cancelled:
                # The coroutine released both shares, its own in `finally` and
                # the kernel's because this work item never entered `run_kernel`.
                return None
            kernel_started = True
        return run_kernel(held, should_resume)

    claim: WorkspaceClaim | None = None
    try:
        held, resume = await _claim_workspace_safely(work_dir, context.attempt)
        claim = held
        result = await asyncio.to_thread(run_kernel_if_not_cancelled, held, resume)
        async with db.acquire() as conn:
            # `complete_job` reads the workspace, so the claim stays held.
            recorded = await repository.complete_job(conn, row, result, context.attempt)
    except asyncio.CancelledError:
        # The lease is gone but the kernel thread keeps running, so stop it.
        abandoned.set()
        with kernel_state_guard:
            kernel_cancelled = True
            kernel_was_started = kernel_started
        if claim is not None and not kernel_was_started:
            # The kernel never started, so its `finally` will not release it.
            claim.release()
        raise
    except AbandonedAttempt as e:
        # A refused write means the fence is working. Stop without retrying or
        # recording a failure.
        logger.warning("Standing down attempt %d: %s", context.attempt, e)
        raise CancelJob(str(e)) from e
    except Exception as e:
        # Finalization failures, including object storage outages, are retryable.
        await _record_failure(compute_job_id, simulation_id, e, context)
        raise
    finally:
        if claim is not None:
            claim.release()

    if not recorded:
        # Keep the workspace so the attempt that took over can resume from it.
        raise CancelJob(
            f"attempt {context.attempt} of compute job {compute_job_id} "
            "no longer owns this job"
        )

    await _remove_finished_workspace(work_dir, compute_job_id)


async def _remove_finished_workspace(work_dir: Path, compute_job_id: uuid.UUID) -> bool:
    """Remove a finished job's workspace; the periodic sweep reclaims a refusal."""
    removed = await asyncio.to_thread(remove_workspace, work_dir)
    if not removed:
        logger.warning(
            "Workspace %s for compute job %s is still held and was not removed "
            "now; it is left to the periodic sweep to reclaim",
            work_dir.name,
            compute_job_id,
        )
    return removed


async def _stand_down(compute_job_id: uuid.UUID, work_dir: Path, attempt: int) -> None:
    """Finish an attempt whose `mark_started` claim was refused.

    Returns for a redelivery of a completed job and raises `CancelJob`
    otherwise.
    """
    async with db.acquire() as conn:
        current = await repository.fetch_by_id(conn, compute_job_id)

    if current is not None and current["status"] == JobStatus.COMPLETED.value:
        # At-least-once delivery: the result is already durable.
        logger.info(
            "Compute job %s is already completed; skipping redelivered attempt %d",
            compute_job_id,
            attempt,
        )
        await _remove_finished_workspace(work_dir, compute_job_id)
        return

    # A newer attempt owns the row, or reconciliation already failed it.
    logger.warning(
        "Compute job %s is not attempt %d's to run (status %s); standing down",
        compute_job_id,
        attempt,
        current["status"] if current is not None else "unknown",
    )
    raise CancelJob(
        f"attempt {attempt} of compute job {compute_job_id} no longer owns this job"
    )


async def _write_progress(
    compute_job_id: uuid.UUID,
    simulation_id: uuid.UUID,
    message: str,
    details: dict[str, Any],
    attempt: int,
) -> bool:
    async with db.acquire() as conn:
        return await repository.record_progress(
            conn, compute_job_id, simulation_id, message, details, attempt
        )


async def _record_failure(
    compute_job_id: uuid.UUID,
    simulation_id: uuid.UUID,
    exc: Exception,
    context: TaskContext,
) -> None:
    """Persist a failed run using the retry decision rqueue is about to make.

    `context.will_retry` reads the job's own attempt budget, which
    `Admin.retry_job` can raise. The registered `TRANSIENT_RETRY` cannot.
    """
    try:
        async with db.acquire() as conn:
            await repository.record_failure(
                conn,
                compute_job_id,
                simulation_id,
                exc,
                step=await repository.get_current_step(conn, compute_job_id),
                will_retry=context.will_retry(exc),
                attempt=context.attempt,
            )
    except Exception:
        # A database outage here must not replace the failure being reported.
        logger.exception("Could not record the failure of job %s", compute_job_id)


async def sweep_abandoned_work_dirs() -> None:
    """Delete terminal-job workspaces older than WORK_DIR_TTL."""
    cutoff = datetime.now().astimezone() - WORK_DIR_TTL
    for simulation_id in await repository.list_abandoned_work_dirs(cutoff):
        await asyncio.to_thread(remove_workspace, JOBS_DIR / simulation_id)


async def _eligible_queue_job_ids(
    admin: Admin, compute_pool: asyncpg.Pool, cutoff: datetime
) -> list[uuid.UUID]:
    """Find old queue rows whose compute jobs are terminal.

    This runs on the worker pool because the purger role cannot read
    `compute.jobs`. Rows with an invalid payload, or a missing or non-terminal
    compute row, are skipped.
    """
    # `admin.schema` is validated by rqueue, so interpolating it is safe.
    async with compute_pool.acquire() as connection:
        rows = await connection.fetch(
            f"""
            WITH candidates AS MATERIALIZED (
                SELECT q.id,
                       (q.payload->>'compute_job_id')::uuid AS compute_job_id,
                       q.finished_at
                FROM {admin.schema}.jobs AS q
                WHERE q.queue = $1
                  AND q.state = ANY($2::text[])
                  AND q.finished_at < $3
                  AND q.payload->>'compute_job_id' ~* $4
            )
            SELECT candidates.id
            FROM candidates
            JOIN compute.jobs AS c ON c.id = candidates.compute_job_id
            WHERE c.status = ANY($5::text[])
            ORDER BY candidates.finished_at
            LIMIT $6
            """,  # noqa: S608
            COMPUTE_QUEUE,
            list(TERMINAL_STATES),
            cutoff,
            JOB_ID_RE,
            list(TERMINAL_STATUSES),
            PURGE_LIMIT,
        )
    return [row["id"] for row in rows]


async def _delete_queue_job_ids(
    admin: Admin, job_ids: list[uuid.UUID], cutoff: datetime
) -> int:
    """Delete the prechecked queue rows using the separately scoped role."""
    if not job_ids:
        return 0
    # `admin.schema` is validated by rqueue, so interpolating it is safe.
    async with admin.pool.acquire() as connection:
        # The purger has DELETE on jobs, and the cascade removes queue history.
        # A single statement deletes the selected IDs atomically.
        removed: int = await connection.fetchval(
            f"""
            WITH removed AS (
                DELETE FROM {admin.schema}.jobs
                WHERE id = ANY($1::uuid[])
                  AND queue = $2
                  AND state = ANY($3::text[])
                  AND finished_at < $4
                RETURNING id
            )
            SELECT count(*)::int FROM removed
            """,  # noqa: S608
            job_ids,
            COMPUTE_QUEUE,
            list(TERMINAL_STATES),
            cutoff,
        )
    return removed


async def purge_finished_jobs(
    admin: Admin, *, compute_pool: asyncpg.Pool | None = None
) -> int:
    """Delete old queue rows whose compute jobs are terminal, and return the count.

    `Admin.purge` cannot express the cross-schema check. Candidates are
    selected on `compute_pool` and deleted on the purger pool behind `admin`.
    A row whose compute job is not terminal stays for reconciliation.
    """
    compute_pool = compute_pool or db.get_pool()
    cutoff = datetime.now(UTC) - JOB_RETENTION
    job_ids = await _eligible_queue_job_ids(admin, compute_pool, cutoff)
    return await _delete_queue_job_ids(admin, job_ids, cutoff)


async def reconcile_terminal_jobs(*, grace: timedelta = RECONCILE_GRACE) -> None:
    """Fail compute jobs that the queue finished without the run reporting.

    See `repository.reconcile_terminal_jobs` for the conditions.
    """
    queue = get_queue()
    reconciled = await repository.reconcile_terminal_jobs(
        queue_schema=queue.schema,
        queue_name=queue.name,
        task=RUN_SIMULATION,
        cutoff=datetime.now().astimezone() - grace,
    )
    for compute_job_id in reconciled:
        # Never routine. Each is a run that ended without reporting, so it
        # belongs in the worker log.
        logger.warning(
            "compute job %s was terminal in the queue but still unfinished; "
            "status reconciled to failed",
            compute_job_id,
        )


async def _run_periodically(
    description: str,
    run_pass: Callable[[], Awaitable[None]],
    stop: asyncio.Event,
    interval: float,
) -> None:
    """Run one maintenance pass on an interval until `stop` is set.

    These are plain asyncio tasks in the worker process, not `rqueue.Scheduler`
    jobs. Each pass is idempotent, so it needs no occurrence key. A failed pass
    is logged and the loop continues, so a database outage does not end
    maintenance for the life of the process.
    """
    while not stop.is_set():
        try:
            await run_pass()
        except Exception:
            logger.exception("%s failed", description)
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(interval):
                await stop.wait()


async def run_periodic_sweep(
    stop: asyncio.Event, *, interval: float = SWEEP_INTERVAL_SECONDS
) -> None:
    """Sweep abandoned workspaces until `stop` is set."""
    await _run_periodically(
        "Sweep of abandoned work directories",
        sweep_abandoned_work_dirs,
        stop,
        interval,
    )


async def run_periodic_reconcile(
    stop: asyncio.Event, *, interval: float = RECONCILE_INTERVAL_SECONDS
) -> None:
    """Reconcile queue-terminal jobs until `stop` is set."""
    await _run_periodically(
        "Reconciliation of queue-terminal jobs",
        reconcile_terminal_jobs,
        stop,
        interval,
    )


async def run_periodic_purge(
    admin: Admin,
    stop: asyncio.Event,
    *,
    compute_pool: asyncpg.Pool | None = None,
    interval: float = PURGE_INTERVAL_SECONDS,
) -> None:
    """Purge finished queue rows until ``stop`` is set."""

    async def purge() -> None:
        removed = await purge_finished_jobs(admin, compute_pool=compute_pool)
        if removed:
            logger.info(
                "purged %d finished queue job(s) older than %s",
                removed,
                JOB_RETENTION,
            )

    await _run_periodically(
        "Purge of finished queue jobs",
        purge,
        stop,
        interval,
    )


def register_tasks(queue: Queue) -> Queue:
    """Register the simulation task on `queue` and return the queue.

    The API and the worker both call this. `Queue.build_insert` reads the
    registration to stamp the retry budget and timeout on each row, so an
    unregistered producer would enqueue jobs with the queue's defaults.
    """
    if RUN_SIMULATION not in queue.tasks:
        queue.register(
            name=RUN_SIMULATION,
            handler=run_simulation_task,
            decoder=decode_payload,
            retry=TRANSIENT_RETRY,
            timeout=RUN_TIMEOUT_SECONDS,
        )
    return queue
