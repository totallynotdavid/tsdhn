"""How the worker process configures and shuts down its rqueue Worker."""

import asyncio
import os
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
