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
from api.core.model_assets import require_model_assets
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
    """Yield the retention pool, credentialed as the purger role.

    The worker role cannot delete queue jobs, and the owner must not be used.
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
            # "wait" would block shutdown on the kernel thread for the length of
            # the simulation.
            executor_shutdown="detach",
        )

        loop = asyncio.get_running_loop()
        for received in (signal.SIGTERM, signal.SIGINT):
            # A simulation outlasts rqueue's shutdown timeout, so it is
            # cancelled and the next worker resumes from the checkpoints.
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
    require_model_assets()
    if NUMBA_THREADS is not None:
        numba.set_num_threads(NUMBA_THREADS)
        logger.info(
            "numba parallel-region thread count capped to %d (TSDHN_NUMBA_THREADS)",
            NUMBA_THREADS,
        )

    asyncio.run(run())

    # An abandoned kernel thread may still run, and CPython would join it on a
    # normal exit. Its writes are fenced, so exit without waiting.
    logging.shutdown()
    os._exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
