import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from rich.console import Console
from rich.logging import RichHandler
from typer.testing import CliRunner

import tsdhn.cli.main as cli_module
from tsdhn.domain import CalculationResponse, TsunamiTravelResponse
from tsdhn.runtime import RuntimeContext

RUNNER = CliRunner()

CALCULATION = CalculationResponse(
    length=10.0,
    width=20.0,
    dislocation=1.5,
    seismic_moment=2.0e18,
    tsunami_warning="warning",
    distance_to_coast=30.0,
    azimuth=40.0,
    dip=50.0,
    epicenter_location="mar",
    rectangle_parameters={},
    rectangle_corners=[],
)

TRAVEL_TIMES = TsunamiTravelResponse(
    arrival_times={"Callao": "12:36 05Aug"},
    distances={"Callao": 19.7},
    epicenter_info={},
)


class _Calculator:
    def __init__(self, _model_dir: Path) -> None:
        pass

    def calculate_earthquake_parameters(
        self, _data: object, _output_dir: Path
    ) -> CalculationResponse:
        return CALCULATION

    def calculate_tsunami_travel_times(self, _data: object) -> TsunamiTravelResponse:
        return TRAVEL_TIMES


def test_calc_command_prints_source_and_arrival_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = RuntimeContext(model_dir=tmp_path, model_version="test", capabilities={})
    monkeypatch.setattr(
        RuntimeContext,
        "resolve",
        classmethod(lambda cls, **kwargs: runtime),
    )
    monkeypatch.setattr(cli_module, "TsunamiCalculator", _Calculator)

    result = RUNNER.invoke(cli_module.app, ["calc", "--model-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Source parameters" in result.output
    assert "Rupture length (km)" in result.output
    assert "Callao" in result.output
    assert "12:36 05Aug" in result.output


def test_run_command_reports_a_failed_simulation_and_keeps_the_run_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_dir = tmp_path / "failed-run"

    def fail(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("model step failed")

    monkeypatch.setattr(cli_module, "run_simulation", fail)

    result = RUNNER.invoke(
        cli_module.app,
        ["run", "--work-dir", str(work_dir)],
    )

    assert result.exit_code == 1
    assert "Simulation failed" in result.output
    assert "Inspect run directory" in result.output
    assert str(work_dir) in result.output


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    saved_level, saved_handlers = root.level, list(root.handlers)
    saved_handler = cli_module._log_handler
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    cli_module._log_handler = saved_handler


@pytest.fixture
def root_level_seen(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    seen: list[int] = []

    class _Store:
        def status(self, _version: str) -> dict[str, object]:
            seen.append(logging.getLogger().level)
            return {}

    monkeypatch.setattr(cli_module, "ModelStore", _Store)
    monkeypatch.setattr(cli_module, "model_version_for_package", lambda v: v or "test")
    return seen


def test_log_level_defaults_to_info(
    monkeypatch: pytest.MonkeyPatch, root_level_seen: list[int]
) -> None:
    monkeypatch.delenv("TSDHN_LOG_LEVEL", raising=False)

    result = RUNNER.invoke(cli_module.app, ["assets", "status"])

    assert result.exit_code == 0, result.output
    assert root_level_seen == [logging.INFO]


def test_log_level_follows_env_var(
    monkeypatch: pytest.MonkeyPatch, root_level_seen: list[int]
) -> None:
    monkeypatch.setenv("TSDHN_LOG_LEVEL", "warning")

    result = RUNNER.invoke(cli_module.app, ["assets", "status"])

    assert result.exit_code == 0, result.output
    assert root_level_seen == [logging.WARNING]


def test_verbose_forces_debug_over_env_var(
    monkeypatch: pytest.MonkeyPatch, root_level_seen: list[int]
) -> None:
    monkeypatch.setenv("TSDHN_LOG_LEVEL", "ERROR")

    result = RUNNER.invoke(cli_module.app, ["-v", "assets", "status"])

    assert result.exit_code == 0, result.output
    assert root_level_seen == [logging.DEBUG]


def test_log_records_go_through_the_shared_console(
    monkeypatch: pytest.MonkeyPatch, root_level_seen: list[int]
) -> None:
    monkeypatch.setenv("TSDHN_LOG_LEVEL", "INFO")
    handler_consoles: list[Console] = []

    class _Store:
        def status(self, _version: str) -> dict[str, object]:
            handler_consoles.extend(
                h.console
                for h in logging.getLogger().handlers
                if isinstance(h, RichHandler)
            )
            return {}

    monkeypatch.setattr(cli_module, "ModelStore", _Store)

    RUNNER.invoke(cli_module.app, ["assets", "status"])

    assert handler_consoles == [cli_module.console]
