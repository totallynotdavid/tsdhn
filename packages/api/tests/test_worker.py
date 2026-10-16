"""How the worker process configures and shuts down its rqueue Worker."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from api import worker as worker_module
from api.core import db

worker_any: Any = worker_module


@pytest.fixture(autouse=True)
def _model_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TSDHN_MODEL_DIR", str(Path(__file__).parents[3] / "model"))


@pytest.mark.asyncio
async def test_the_worker_detaches_from_its_blocking_threads_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown must not wait for the kernel thread, which cannot be stopped."""
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
    monkeypatch.setattr(db, "runtime_dsn", lambda *_args: "postgresql://test")

    await asyncio.wait_for(worker_module.run(), timeout=10)

    assert captured["executor_shutdown"] == "detach"


def test_main_exits_the_process_instead_of_joining_abandoned_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CPython joins non-daemon executor threads at exit, so `main()` hard-exits."""
    calls: list[Any] = []

    def fake_run(coro: Any) -> None:
        coro.close()
        calls.append("run")

    def fake_exit(code: int) -> None:
        calls.append(("exit", code))

    monkeypatch.setattr(worker_any.asyncio, "run", fake_run)
    monkeypatch.setattr(os, "_exit", fake_exit)

    worker_module.main()

    assert calls == ["run", ("exit", 0)]


def test_the_shutdown_story_holds_together(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detach and the hard exit only make sense together, so assert both."""
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
    monkeypatch.setattr(db, "runtime_dsn", lambda *_args: "postgresql://test")
    monkeypatch.setattr(os, "_exit", exits.append)

    worker_module.main()

    assert captured["executor_shutdown"] == "detach"
    assert exits == [0]


async def _run_worker_recording_maintenance(
    monkeypatch: pytest.MonkeyPatch, *, retention: bool
) -> list[str]:
    started: list[str] = []

    class _Worker:
        def __init__(self, _queue: Any, **_kwargs: Any) -> None:
            return None

        def stop(self) -> None:
            return None

        async def run(self) -> None:
            await asyncio.sleep(0)

    def recorder(name: str) -> Any:
        async def run_pass(*_args: Any, **_kwargs: Any) -> None:
            started.append(name)

        return run_pass

    @asynccontextmanager
    async def purge_pool() -> AsyncIterator[object]:
        started.append("purger pool")
        yield object()

    async def open_pool(**_kwargs: Any) -> object:
        return object()

    async def close_pool() -> None:
        return None

    async def ensure_output_bucket() -> None:
        return None

    monkeypatch.setattr(worker_any, "RETENTION_ENABLED", retention)
    monkeypatch.setattr(worker_any, "OUTPUT_RETENTION_DAYS", 90)
    monkeypatch.setattr(worker_any, "Worker", _Worker)
    monkeypatch.setattr(worker_any, "Admin", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(worker_any, "build_queue", lambda _pool: object())
    monkeypatch.setattr(worker_any, "register_tasks", lambda queue: queue)
    monkeypatch.setattr(worker_any, "ensure_output_bucket", ensure_output_bucket)
    monkeypatch.setattr(worker_any, "purge_pool", purge_pool)
    for name in ("sweep", "reconcile", "purge", "expiry"):
        monkeypatch.setattr(worker_any, f"run_periodic_{name}", recorder(name))
    monkeypatch.setattr(db, "open_pool", open_pool)
    monkeypatch.setattr(db, "close_pool", close_pool)
    monkeypatch.setattr(db, "runtime_dsn", lambda *_args: "postgresql://test")

    await asyncio.wait_for(worker_module.run(), timeout=10)
    return started


@pytest.mark.asyncio
async def test_a_worker_with_retention_off_runs_neither_retention_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = await _run_worker_recording_maintenance(monkeypatch, retention=False)

    assert sorted(started) == ["reconcile", "sweep"]


@pytest.mark.asyncio
async def test_a_worker_with_retention_on_runs_both_retention_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = await _run_worker_recording_maintenance(monkeypatch, retention=True)

    assert sorted(started) == ["expiry", "purge", "purger pool", "reconcile", "sweep"]
