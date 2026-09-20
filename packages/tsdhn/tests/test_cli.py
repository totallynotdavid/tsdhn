import json
import logging
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path

import pytest
from rich.console import Console
from rich.logging import RichHandler
from typer.testing import CliRunner

import tsdhn.cli.main as cli_module
from tsdhn.assets import ModelDataset
from tsdhn.domain import CalculationResponse, TsunamiTravelResponse
from tsdhn.engine import OutputFile, SimulationOutputs, SimulationResult
from tsdhn.runtime import CapabilityStatus, RuntimeContext

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


def _simulation_result(work_dir: Path) -> SimulationResult:
    return SimulationResult(
        calculation=CALCULATION,
        travel_times=TRAVEL_TIMES,
        runtime=RuntimeContext(
            model_dir=work_dir, model_version="test", capabilities={}
        ),
        outputs=SimulationOutputs(
            root=work_dir,
            files=(
                OutputFile(
                    name="source",
                    path=work_dir / "source.json",
                    content_type="application/json",
                ),
            ),
        ),
    )


def test_run_command_prints_results_and_output_files_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_dir = tmp_path / "ok-run"

    def simulate(
        _data: object, work_dir: Path, *, on_progress: object, **_kwargs: object
    ) -> SimulationResult:
        return _simulation_result(work_dir)

    monkeypatch.setattr(cli_module, "run_simulation", simulate)

    result = RUNNER.invoke(cli_module.app, ["run", "--work-dir", str(work_dir)])

    assert result.exit_code == 0, result.output
    assert "TSDHN simulation" in result.output
    assert "Rupture length (km)" in result.output
    assert "Simulation complete." in result.output
    assert f"source: {work_dir / 'source.json'}" in result.output.replace("\n", "")


def test_run_command_defaults_the_work_dir_to_a_timestamped_jobs_folder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Path] = []

    def simulate(_data: object, work_dir: Path, **_kwargs: object) -> SimulationResult:
        seen.append(work_dir)
        return _simulation_result(work_dir)

    monkeypatch.setattr(cli_module, "run_simulation", simulate)

    result = RUNNER.invoke(cli_module.app, ["run"])

    assert result.exit_code == 0, result.output
    (work_dir,) = seen
    assert work_dir.parent == Path("jobs")
    assert len(work_dir.name) == len("YYYYmmdd-HHMMSS")


@pytest.mark.parametrize(
    ("details", "shown"),
    [
        ({"step_index": 2, "total_steps": 5}, "[2/5] Running step"),
        ({}, "Running step"),
    ],
)
def test_run_command_shows_progress_messages_with_step_counts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    details: dict[str, object],
    shown: str,
) -> None:
    def simulate(
        _data: object, work_dir: Path, *, on_progress: object, **_kwargs: object
    ) -> SimulationResult:
        on_progress("Running step", details)  # type: ignore[operator]
        return _simulation_result(work_dir)

    monkeypatch.setattr(cli_module, "run_simulation", simulate)

    result = RUNNER.invoke(cli_module.app, ["run", "--work-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert shown in result.output
    assert ("[2/5]" in result.output) == ("step_index" in details)


def test_run_command_reports_invalid_parameters_with_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def reject(*_args: object, **_kwargs: object) -> object:
        raise ValueError("Mw out of range")

    monkeypatch.setattr(cli_module, "run_simulation", reject)

    result = RUNNER.invoke(cli_module.app, ["run", "--work-dir", str(tmp_path)])

    assert result.exit_code == 2
    assert "Invalid parameters" in result.output
    assert "Mw out of range" in result.output
    assert "Simulation failed" not in result.output


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


def _capabilities() -> dict[str, CapabilityStatus]:
    return {
        "gmt": CapabilityStatus(name="gmt", available=True, version="6.5.0"),
        "grdmath": CapabilityStatus(name="grdmath", available=True, path="/bin/gm"),
        "tool": CapabilityStatus(name="tool", available=False, detail="not found"),
        "bare": CapabilityStatus(name="bare", available=False),
    }


def test_doctor_reports_the_model_and_capabilities_when_the_runtime_resolves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = RuntimeContext(
        model_dir=Path("/models/v1"), model_version="v1", capabilities=_capabilities()
    )
    monkeypatch.setattr(
        RuntimeContext, "resolve", classmethod(lambda cls, **kwargs: runtime)
    )

    result = RUNNER.invoke(cli_module.app, ["doctor"])

    assert result.exit_code == 0, result.output
    rows = {
        cells[0]: cells[1:]
        for line in result.output.splitlines()
        if len(cells := [c.strip() for c in line.split("│")[1:-1]]) == 3
    }
    assert rows["model"] == ["available", "/models/v1"]
    assert rows["gmt"] == ["available", "6.5.0"]
    assert rows["grdmath"] == ["available", "/bin/gm"]
    assert rows["tool"] == ["missing", "not found"]
    assert rows["bare"] == ["missing", ""]


def test_doctor_reports_a_missing_model_and_still_checks_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unresolvable(cls: object, **_kwargs: object) -> RuntimeContext:
        raise FileNotFoundError("no model here")

    monkeypatch.setattr(RuntimeContext, "resolve", classmethod(unresolvable))
    monkeypatch.setattr(cli_module, "check_capabilities", _capabilities)

    result = RUNNER.invoke(cli_module.app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "model" in result.output
    assert "missing" in result.output
    assert "no model here" in result.output
    assert "6.5.0" in result.output


class _RecordingStore:
    installs: list[tuple[str, dict[str, object]]]

    def __init__(self) -> None:
        pass

    def status(self, model_version: str) -> dict[str, object]:
        return {"version": model_version, "installed": False}

    def install(self, model_version: str, **options: object) -> ModelDataset:
        type(self).installs.append((model_version, options))
        return ModelDataset(
            version=model_version, path=Path("/models") / model_version, managed=True
        )


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> type[_RecordingStore]:
    _RecordingStore.installs = []
    monkeypatch.setattr(cli_module, "ModelStore", _RecordingStore)
    return _RecordingStore


def test_assets_status_prints_the_store_status_for_the_requested_version(
    store: type[_RecordingStore],
) -> None:
    result = RUNNER.invoke(
        cli_module.app, ["assets", "status", "--model-version", "1.2.3"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"version": "1.2.3", "installed": False}


def test_assets_status_defaults_to_the_package_version(
    store: type[_RecordingStore],
) -> None:
    result = RUNNER.invoke(cli_module.app, ["assets", "status"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["version"] == version("tsdhn")


def test_assets_install_forwards_url_sha256_and_force_to_the_store(
    store: type[_RecordingStore],
) -> None:
    result = RUNNER.invoke(
        cli_module.app,
        [
            "assets",
            "install",
            "--model-version",
            "1.2.3",
            "--url",
            "https://example.test/model.tar.gz",
            "--sha256",
            "abc123",
            "--force",
        ],
    )

    assert result.exit_code == 0, result.output
    assert store.installs == [
        (
            "1.2.3",
            {
                "url": "https://example.test/model.tar.gz",
                "sha256": "abc123",
                "force": True,
            },
        )
    ]
    assert "Installed model 1.2.3" in result.output
    assert "/models/1.2.3" in result.output


def test_assets_install_defaults_to_no_overrides_for_the_package_version(
    store: type[_RecordingStore],
) -> None:
    result = RUNNER.invoke(cli_module.app, ["assets", "install"])

    assert result.exit_code == 0, result.output
    assert store.installs == [
        (version("tsdhn"), {"url": None, "sha256": None, "force": False})
    ]


def test_repeated_invocations_do_not_stack_log_handlers(
    root_level_seen: list[int],
) -> None:
    RUNNER.invoke(cli_module.app, ["assets", "status"])
    RUNNER.invoke(cli_module.app, ["assets", "status"])

    rich_handlers = [
        h for h in logging.getLogger().handlers if isinstance(h, RichHandler)
    ]
    assert len(rich_handlers) == 1
