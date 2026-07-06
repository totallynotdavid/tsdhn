import shutil
import subprocess
from pathlib import Path

from core.config import ProcessingStep
from core.utils.file_utils import make_executable, validate_files

__all__ = ["ProcessingStep", "handle_command_step", "process_step"]


def process_step(
    step: ProcessingStep, working_dir: Path, tools_dir: Path | None
) -> None:
    if step.python_callable:
        step.python_callable(working_dir)
    else:
        handle_command_step(step, working_dir, tools_dir)
    validate_files(working_dir, step.file_checks)


def handle_command_step(
    step: ProcessingStep, working_dir: Path, tools_dir: Path | None
) -> None:
    if step.command is not None:
        if tools_dir is None:
            raise RuntimeError(
                f"Step '{step.name}' requires TSDHN_TOOLS_DIR with "
                "prebuilt executables."
            )
        executable_name = Path(step.command[0]).name
        source = tools_dir / executable_name
        if not source.is_file():
            raise FileNotFoundError(f"Required model executable missing: {source}")
        shutil.copy2(source, working_dir / executable_name)

        cmd_path = working_dir / step.command[0]
        make_executable(cmd_path)
        subprocess.run(step.command, cwd=working_dir, check=True)
