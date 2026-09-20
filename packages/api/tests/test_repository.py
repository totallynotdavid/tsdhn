import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from api.core.repository import record_failure, status_from_row
from tsdhn.domain import JobStatus

CREATED = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": uuid.uuid4(),
        "simulation_id": uuid.uuid4(),
        "status": JobStatus.QUEUED.value,
        "input_params": {},
        "details": "Queued for simulation worker",
        "step": None,
        "step_index": None,
        "total_steps": None,
        "calculation": None,
        "travel_times": None,
        "outputs": [],
        "error": None,
        "created_at": CREATED,
        "updated_at": CREATED,
        "started_at": None,
        "finished_at": None,
    }
    return row | overrides


def test_status_exposes_output_names_only() -> None:
    status = status_from_row(
        _row(
            status=JobStatus.COMPLETED.value,
            outputs=[
                {
                    "name": "max_height_map",
                    "key": "simulations/abc/outputs/maxola.pdf",
                    "filename": "maxola.pdf",
                    "content_type": "application/pdf",
                }
            ],
        )
    )

    assert status["outputs"] == ["max_height_map"]
    assert "simulations/abc" not in str(status)


def test_status_has_no_outputs_before_completion() -> None:
    assert status_from_row(_row())["outputs"] == []


def test_status_handles_a_null_outputs_column() -> None:
    assert status_from_row(_row(outputs=None))["outputs"] == []


def test_status_serializes_timestamps_as_iso_strings() -> None:
    status = status_from_row(_row(started_at=CREATED))

    assert status["created_at"] == CREATED.isoformat()
    assert status["started_at"] == CREATED.isoformat()
    assert status["finished_at"] is None


def test_status_carries_step_progress() -> None:
    status = status_from_row(
        _row(
            status=JobStatus.RUNNING.value, step="tsunami", step_index=3, total_steps=8
        )
    )

    assert (status["step"], status["step_index"], status["total_steps"]) == (
        "tsunami",
        3,
        8,
    )


class _RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def transaction(self) -> _RecordingConnection:
        return self

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def execute(self, *args: Any) -> None:
        self.calls.append(args)


@pytest.mark.asyncio
@pytest.mark.parametrize("will_retry", [False, True])
async def test_failure_keeps_server_paths_out_of_the_client_status(
    caplog: pytest.LogCaptureFixture, will_retry: bool
) -> None:
    path = "/home/dubu/picv-2025/jobs/0b7c/tsunami"
    conn = _RecordingConnection()

    with caplog.at_level(logging.ERROR, logger="api.core.repository"):
        try:
            raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")
        except FileNotFoundError as exc:
            await record_failure(
                conn,
                uuid.uuid4(),
                uuid.uuid4(),
                exc,
                step="tsunami",
                will_retry=will_retry,
                attempt=1,
            )

    # Every parameter written to compute.jobs is what a client can read back.
    written = " ".join(str(arg) for call in conn.calls for arg in call)
    assert path not in written
    assert "/home/dubu" not in written
    assert "FileNotFoundError" in written

    # The full detail stays in the server log.
    assert path in caplog.text
