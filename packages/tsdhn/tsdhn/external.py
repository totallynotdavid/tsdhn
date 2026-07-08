import shutil
from collections.abc import Iterable
from functools import cache
from pathlib import Path

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


def ensure_executables(names: Iterable[str] = REQUIRED_EXECUTABLES) -> None:
    required = tuple(dict.fromkeys(names))
    for name in required:
        resolve(name)
