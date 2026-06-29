import shutil
from functools import cache
from pathlib import Path

# The Fortran compiler is intentionally omitted: each `ProcessingStep`
# declares its own `compiler` in `CompilerConfig`, which is resolved on
# demand per step.
REQUIRED_EXECUTABLES: tuple[str, ...] = ("gmt", "pdflatex", "ttt_client")


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


def ensure_all() -> None:
    for name in REQUIRED_EXECUTABLES:
        resolve(name)
