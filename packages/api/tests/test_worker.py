"""How the worker process configures and shuts down its rqueue Worker."""

import asyncio
import os
from typing import Any

import pytest

from api import worker as worker_module
from api.core import db

worker_any: Any = worker_module


@pytest.mark.asyncio
async def test_the_worker_detaches_from_its_blocking_threads_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown must not wait for a thread that cannot be stopped.

    The simulation kernel runs on a thread through `asyncio.to_thread`, and
    Python cannot kill a thread. Under rqueue's default `executor_shutdown=
    "wait"`, tearing down the bounded executor blocks until that thread
    finishes on its own -- measured at 3.00s for a 3s kernel against a
    coroutine cancelled at 0.00s. `run()` would then not return for as long as
    the simulation takes, so the `finally` that closes the pool never runs and
    only the orchestrator's SIGKILL ends the process.

    `detach` does not stop the thread; it stops waiting for it, once the leases
    are already handed back. That is safe here precisely because the process is
    exiting: `run()` returns into `main()` and the loop closes behind it.
    """
    captured: dict[str, Any] = {}

    class _Worker:
        def __init__(self, _queue: Any, **kwargs: Any) -> None:
            captured.update(kwargs)

        def stop(self) -> None:
            return None

        async def run(self) -> None:
            return None

    async def open_pool(**_kwargs: Any) -> object:
        return object()

    async def close_pool() -> None:
        return None

    monkeypatch.setattr(worker_any, "Worker", _Worker)
    monkeypatch.setattr(worker_any, "build_queue", lambda _pool: object())
    monkeypatch.setattr(worker_any, "register_tasks", lambda queue: queue)
    monkeypatch.setattr(db, "open_pool", open_pool)
    monkeypatch.setattr(db, "close_pool", close_pool)

    await asyncio.wait_for(worker_module.run(), timeout=10)

    assert captured["executor_shutdown"] == "detach"


def test_main_exits_the_process_instead_of_joining_abandoned_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detach is only half a fix if the process then hangs on its way out.

    `executor_shutdown="detach"` stops rqueue waiting for the abandoned kernel
    thread, but that thread belongs to a ThreadPoolExecutor and is therefore
    non-daemon, and CPython joins every non-daemon thread during interpreter
    shutdown. Returning normally from `main()` parks the process for the rest
    of the simulation -- 3.20s for a 3s thread, against 0.16s with the hard
    exit -- which is the same wait, relocated from rqueue's executor teardown
    into Python's own atexit machinery.

    So `main()` must not fall off the end. The real call would take this test
    process with it, hence the stub.
    """
    calls: list[Any] = []

    def fake_run(coro: Any) -> None:
        # Close it so the loop-less coroutine does not warn about never
        # being awaited; the point here is what happens after run() returns.
        coro.close()
        calls.append("run")

    def fake_exit(code: int) -> None:
        calls.append(("exit", code))

    monkeypatch.setattr(worker_any.asyncio, "run", fake_run)
    monkeypatch.setattr(os, "_exit", fake_exit)

    worker_module.main()

    assert calls == ["run", ("exit", 0)]


def test_the_shutdown_story_holds_together(monkeypatch: pytest.MonkeyPatch) -> None:
    """The two halves are only correct as a pair, so assert them as a pair.

    Detach without the hard exit relocates the hang; the hard exit without
    detach is unnecessary and would be cargo cult. Either one alone reads as
    defensible, which is exactly why a later change could drop one and leave
    the other looking deliberate.
    """
    captured: dict[str, Any] = {}

    class _Worker:
        def __init__(self, _queue: Any, **kwargs: Any) -> None:
            captured.update(kwargs)

        def stop(self) -> None:
            return None

        async def run(self) -> None:
            return None

    async def open_pool(**_kwargs: Any) -> object:
        return object()

    async def close_pool() -> None:
        return None

    exits: list[int] = []
    monkeypatch.setattr(worker_any, "Worker", _Worker)
    monkeypatch.setattr(worker_any, "build_queue", lambda _pool: object())
    monkeypatch.setattr(worker_any, "register_tasks", lambda queue: queue)
    monkeypatch.setattr(db, "open_pool", open_pool)
    monkeypatch.setattr(db, "close_pool", close_pool)
    monkeypatch.setattr(os, "_exit", exits.append)

    worker_module.main()

    assert captured["executor_shutdown"] == "detach"
    assert exits == [0]
