import asyncio
import logging
import os
import signal
import socket

import numba
from rqueue import Worker

from api.core import db
from api.core.queue import build_queue
from api.core.settings import (
    COMPUTE_QUEUE,
    LOG_LEVEL,
    NUMBA_THREADS,
    WORKER_CONCURRENCY,
    WORKER_ID,
    WORKER_LEASE_SECONDS,
    worker_pool_size,
)
from api.core.tasks import (
    register_tasks,
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


async def run() -> None:
    min_size, max_size = worker_pool_size()
    pool = await db.open_pool(min_size=min_size, max_size=max_size)
    try:
        worker = Worker(
            register_tasks(build_queue(pool)),
            worker_id=worker_id(),
            concurrency=WORKER_CONCURRENCY,
            lease_duration=WORKER_LEASE_SECONDS,
            # The simulation kernel runs on a thread, and Python cannot kill a
            # thread. Under the default "wait", shutdown blocks on that thread
            # for as long as the simulation takes -- tens of minutes -- so
            # run() never returns and the `finally` below never closes the
            # pool. "detach" stops waiting once the leases are back.
            executor_shutdown="detach",
        )

        loop = asyncio.get_running_loop()
        for received in (signal.SIGTERM, signal.SIGINT):
            # stop() stops claiming and gives in-flight work a bounded grace
            # period (rqueue's shutdown_timeout, 30s by default). A simulation
            # runs for tens of minutes, so in practice it does not finish:
            # rqueue cancels it and hands the lease straight back as `pending`
            # rather than leaving it to expire, and the next worker picks it up
            # and resumes from the checkpoints in its work directory.
            #
            # Detach mode (above) is what makes the rest of this shutdown
            # reachable: run() returns once the leases are back, so the pool is
            # closed properly instead of the process sitting on an open pool
            # until it is killed. It does not stop the abandoned kernel thread
            # -- nothing can -- it only stops waiting for it, which is why the
            # process must not be reused afterwards. It is not: run() returns
            # into main(), and the loop closes behind it. The thread then fails
            # at its next progress write, whose loop is gone, and unwinds there.
            loop.add_signal_handler(received, worker.stop)

        # The worker process owns maintenance because it is the process that
        # owns recovery: reconciliation exists to repair the compute.jobs rows
        # rqueue's own lease recovery leaves behind.
        stop_maintenance = asyncio.Event()
        maintenance = [
            asyncio.create_task(run_periodic_sweep(stop_maintenance)),
            asyncio.create_task(run_periodic_reconcile(stop_maintenance)),
        ]
        logger.info("simulation worker serving queue %s", COMPUTE_QUEUE)
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
        # Numba lacks type stubs; suppress type checking.
        numba.set_num_threads(NUMBA_THREADS)  # type: ignore[no-untyped-call]
        logger.info(
            "numba parallel-region thread count capped to %d (TSDHN_NUMBA_THREADS)",
            NUMBA_THREADS,
        )

    asyncio.run(run())

    # run() returning means the leases are handed back and the pool is closed.
    # It does not mean the process is idle: the worker runs with
    # executor_shutdown="detach" (see run()), so an abandoned kernel thread can
    # still be alive, and Python cannot kill it.
    #
    # Those threads belong to a ThreadPoolExecutor, which makes them
    # non-daemon, and CPython joins every non-daemon thread during interpreter
    # shutdown. Falling off the end of main() therefore parks the process for
    # the rest of the simulation -- measured at 3.20s for a 3s thread, against
    # 0.16s with this call -- which is the very wait detach mode exists to
    # avoid, moved from rqueue's executor teardown into Python's own atexit
    # machinery. Detaching is only safe because the process is exiting rather
    # than being reused, so the process has to actually exit.
    #
    # Nothing durable is lost by leaving that way: the leases are back, the
    # pool is closed, and the abandoned thread's writes are fenced and would be
    # refused anyway. os._exit skips the buffers logging would otherwise flush
    # on the way out, so flush them here.
    logging.shutdown()
    os._exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
