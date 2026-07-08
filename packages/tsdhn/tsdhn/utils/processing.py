from pathlib import Path

from tsdhn.pipeline.types import ProcessingStep
from tsdhn.utils.file_utils import validate_files

__all__ = ["process_step"]


def process_step(
    step: ProcessingStep, working_dir: Path, tools_dir: Path | None
) -> None:
    step.runner.run(working_dir, tools_dir)
    validate_files(working_dir, step.file_checks)
