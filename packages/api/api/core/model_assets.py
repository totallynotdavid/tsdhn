"""Fail a process at start when the model assets it needs are not installed."""

from tsdhn.runtime import RuntimeContext

__all__ = ["require_model_assets"]


def require_model_assets() -> None:
    """Exit with the engine's own message instead of failing on the first job."""
    try:
        RuntimeContext.resolve()
    except RuntimeError as error:
        raise SystemExit(f"error: {error}") from error
