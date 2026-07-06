import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.calculator import TsunamiCalculator
from core.config import MASTER_PIPELINE
from core.executables import ensure_all
from core.runtime import RuntimePaths
from core.schemas import CalculationResponse, EarthquakeInput, TsunamiTravelResponse
from core.utils.file_utils import prepare_simulation_workspace
from core.utils.processing import process_step

__all__ = ["ProgressCallback", "SimulationResult", "run_simulation"]

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, dict[str, Any]], None]


def _noop(_message: str, _details: dict[str, Any]) -> None:
    return None


@dataclass(frozen=True)
class SimulationResult:
    calculation: CalculationResponse
    travel_times: TsunamiTravelResponse
    report_path: Path


def run_simulation(
    data: EarthquakeInput,
    work_dir: Path,
    *,
    model_dir: Path | None = None,
    tools_dir: Path | None = None,
    skip_steps: list[str] | None = None,
    on_progress: ProgressCallback = _noop,
) -> SimulationResult:
    """
    Run the full TSDHN pipeline in `work_dir` and return its artifacts.

    Parameters:
        data: Validated earthquake input.
        work_dir: Per-run working directory prepared with required model inputs.
        model_dir: Explicit model asset directory. If omitted, `TSDHN_MODEL_DIR`
            is required.
        tools_dir: Explicit prebuilt executable directory. If omitted,
            `TSDHN_TOOLS_DIR` is required only when active command steps need it.
        skip_steps: Pipeline step names to skip (e.g. for fast iteration).
        on_progress: Called before each phase/step with `(message, details)`.

    Raises:
        Any exception from a pipeline step. The caller owns `work_dir` and is
        responsible for cleanup/inspection on failure.
    """
    skip_steps = skip_steps or []
    _validate_skip_steps(skip_steps)
    active_steps = [step for step in MASTER_PIPELINE if step.name not in skip_steps]
    required_tools = tuple(
        Path(step.command[0]).name for step in active_steps if step.command is not None
    )
    runtime = RuntimePaths.resolve(
        model_dir=model_dir,
        tools_dir=tools_dir,
        require_tools=bool(required_tools),
        required_tools=required_tools,
    )

    calculator = TsunamiCalculator(runtime.model_dir)
    prepare_simulation_workspace(runtime.model_dir, work_dir)

    # The legacy pipeline reads hypo.dat from the run workspace.
    on_progress("Running earthquake calculations", {})
    calculation = calculator.calculate_earthquake_parameters(data, work_dir)
    on_progress(
        "Earthquake calculations complete",
        {"calculation": calculation.model_dump()},
    )

    on_progress("Calculating tsunami travel times", {})
    travel_times = calculator.calculate_tsunami_travel_times(data)
    on_progress(
        "Tsunami calculations complete",
        {"travel_times": travel_times.model_dump()},
    )

    ensure_all(active_steps)
    total_steps = len(active_steps)
    for index, step in enumerate(active_steps, start=1):
        on_progress(
            f"Processing {step.name}",
            {"step": step.name, "step_index": index, "total_steps": total_steps},
        )
        step_dir = work_dir / step.working_dir if step.working_dir else work_dir
        step_dir.mkdir(parents=True, exist_ok=True)
        process_step(step, step_dir, runtime.tools_dir)

    report_path = work_dir / "reporte.pdf"
    on_progress("Simulation completed successfully", {})
    return SimulationResult(
        calculation=calculation,
        travel_times=travel_times,
        report_path=report_path,
    )


def _validate_skip_steps(skip_steps: list[str]) -> None:
    valid = {step.name for step in MASTER_PIPELINE}
    invalid = set(skip_steps) - valid
    if invalid:
        raise ValueError(f"Invalid steps to skip: {', '.join(sorted(invalid))}")
