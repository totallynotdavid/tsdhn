import shutil
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tsdhn.steps import ProcessingStep

REQUIRED_EXECUTABLES: tuple[str, ...] = ("gmt", "ttt_client")


@cache
def resolve(name: str) -> Path:
    """Return the absolute path to `name` as resolved by `PATH`."""
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(
            f"Required executable '{name}' not found on PATH. "
            f"Install it or update PATH before starting a job."
        )
    return Path(path)


def ensure_all(steps: Iterable[ProcessingStep] | None = None) -> None:
    required = (
        REQUIRED_EXECUTABLES
        if steps is None
        else tuple(
            sorted(
                {executable for step in steps for executable in step.system_executables}
            )
        )
    )
    for name in required:
        resolve(name)
