import asyncio
import logging
import os
import signal
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
import numba
from rqueue import Admin, Worker

from api.core import db
from api.core.queue import build_queue
from api.core.settings import (
    COMPUTE_PURGER_PASSWORD,
    COMPUTE_PURGER_ROLE,
    COMPUTE_QUEUE,
    COMPUTE_QUEUE_SCHEMA,
    COMPUTE_WORKER_PASSWORD,
    COMPUTE_WORKER_ROLE,
    LOG_LEVEL,
    NUMBA_THREADS,
    WORKER_CONCURRENCY,
    WORKER_ID,
    WORKER_LEASE_SECONDS,
    worker_pool_size,
)
from api.core.tasks import (
    register_tasks,
    run_periodic_purge,
    run_periodic_reconcile,
    run_periodic_sweep,
)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def worker_id() -> str:
    """Name this worker so its heartbeats and leases are attributable."""
    if WORKER_ID:
        return WORKER_ID
    # rqueue restricts a worker id to letters, digits, '_', '.', ':' and '-'.
    host = "".join(
        c if c.isalnum() or c in "_.-" else "-" for c in socket.gethostname()
    )
    return f"tsdhn-worker-{host or 'unknown'}-{os.getpid()}"[:128]


@asynccontextmanager
async def purge_pool() -> AsyncIterator[asyncpg.Pool]:
    """Yield the pool used by retention, credentialed separately from consume.

    The purger password is required. The worker pool uses the CONSUME role,
    which cannot delete queue jobs, and falling back to the owner would bypass
    every runtime boundary.
    """
    # Retention is hourly, so one lazy connection is enough.
    pool = await asyncpg.create_pool(
        db.runtime_dsn(COMPUTE_PURGER_ROLE, COMPUTE_PURGER_PASSWORD),
        min_size=0,
        max_size=1,
        timeout=db.CONNECT_TIMEOUT,
    )
    try:
        yield pool
    finally:
        await pool.close()


async def run() -> None:
    min_size, max_size = worker_pool_size()
    pool = await db.open_pool(
        min_size=min_size,
        max_size=max_size,
        dsn=db.runtime_dsn(COMPUTE_WORKER_ROLE, COMPUTE_WORKER_PASSWORD),
    )
    try:
        worker = Worker(
            register_tasks(build_queue(pool)),
            worker_id=worker_id(),
            concurrency=WORKER_CONCURRENCY,
            lease_duration=WORKER_LEASE_SECONDS,
            # The kernel runs on a thread that Python cannot kill. With the
            # default "wait", shutdown blocks on that thread for the length of
            # the simulation, so `run()` never returns and the `finally` below
            # never closes the pool. "detach" stops waiting once the leases are
            # back.
            executor_shutdown="detach",
        )

        loop = asyncio.get_running_loop()
        for received in (signal.SIGTERM, signal.SIGINT):
            # `stop()` stops claiming and gives in-flight work rqueue's
            # `shutdown_timeout` (30 seconds by default). A simulation runs for
            # tens of minutes, so rqueue cancels it and returns the lease as
            # `pending`. The next worker resumes from the checkpoints in the
            # work directory.
            #
            # "detach" lets `run()` return once the leases are back, so the
            # pool closes. It does not stop the abandoned kernel thread. That
            # thread fails at its next progress write because its loop is gone.
            loop.add_signal_handler(received, worker.stop)

        stop_maintenance = asyncio.Event()
        logger.info("simulation worker serving queue %s", COMPUTE_QUEUE)
        async with purge_pool() as retention_pool:
            maintenance = [
                asyncio.create_task(run_periodic_sweep(stop_maintenance)),
                asyncio.create_task(run_periodic_reconcile(stop_maintenance)),
                asyncio.create_task(
                    run_periodic_purge(
                        Admin(retention_pool, schema=COMPUTE_QUEUE_SCHEMA),
                        stop_maintenance,
                        compute_pool=pool,
                    )
                ),
            ]
            try:
                await worker.run()
            finally:
                stop_maintenance.set()
                for task in maintenance:
                    task.cancel()
                await asyncio.gather(*maintenance, return_exceptions=True)
    finally:
        await db.close_pool()


def main() -> None:  # pragma: no cover
    if NUMBA_THREADS is not None:
        # Numba lacks type stubs, so suppress type checking.
        numba.set_num_threads(NUMBA_THREADS)  # type: ignore[no-untyped-call]
        logger.info(
            "numba parallel-region thread count capped to %d (TSDHN_NUMBA_THREADS)",
            NUMBA_THREADS,
        )

    asyncio.run(run())

    # `run()` returning means the leases are back and the pool is closed. An
    # abandoned kernel thread can still be alive because the worker runs with
    # `executor_shutdown="detach"`.
    #
    # Executor threads are non-daemon, and CPython joins every non-daemon
    # thread during interpreter shutdown. Returning from `main()` would park
    # the process until the simulation ends, which is the wait "detach" exists
    # to avoid. Detaching is safe only because the process exits instead of
    # being reused.
    #
    # Nothing durable is lost. The leases are back, the pool is closed, and the
    # abandoned thread's writes are fenced. `os._exit` skips the log flush, so
    # flush first.
    logging.shutdown()
    os._exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
