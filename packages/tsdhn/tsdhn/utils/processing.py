import shutil
import subprocess
from pathlib import Path

from tsdhn.pipeline.types import ProcessingStep, PythonRunner, ToolRunner
from tsdhn.utils.file_utils import make_executable, validate_files

__all__ = ["handle_tool_step", "process_step"]


def process_step(
    step: ProcessingStep, working_dir: Path, tools_dir: Path | None
) -> None:
    match step.runner:
        case PythonRunner(fn=fn):
            fn(working_dir)
        case ToolRunner():
            handle_tool_step(step, working_dir, tools_dir)
    validate_files(working_dir, step.file_checks)


def handle_tool_step(
    step: ProcessingStep, working_dir: Path, tools_dir: Path | None
) -> None:
    if not isinstance(step.runner, ToolRunner):
        raise TypeError(f"Step '{step.name}' does not use a tool runner.")
    if tools_dir is None:
        raise RuntimeError(
            f"Step '{step.name}' requires TSDHN_TOOLS_DIR with prebuilt executables."
        )

    executable_name = step.runner.executable
    source = tools_dir / executable_name
    if not source.is_file():
        raise FileNotFoundError(f"Required model executable missing: {source}")

    shutil.copy2(source, working_dir / executable_name)
    make_executable(working_dir / executable_name)
    subprocess.run(
        [f"./{executable_name}", *step.runner.args],
        cwd=working_dir,
        check=True,
    )
