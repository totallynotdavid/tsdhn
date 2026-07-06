import os
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "REQUIRED_MODEL_DIRS",
    "REQUIRED_MODEL_FILES",
    "REQUIRED_TOOL_EXECUTABLES",
    "RuntimePaths",
    "model_dir_from_env",
    "tools_dir_from_env",
    "validate_model_dir",
    "validate_tools_dir",
]

REQUIRED_MODEL_DIRS: tuple[str, ...] = ("bathy", "ttt_mundo")
REQUIRED_MODEL_FILES: tuple[str, ...] = (
    "pacifico.mat",
    "maper1.mat",
    "mecfoc.dat",
    "puertos.txt",
    "tidal.dat",
    "bathy/grid_a.grd",
    "bathy/xa.dat",
    "bathy/ya.dat",
    "ttt_mundo/cortado.i2",
)
REQUIRED_TOOL_EXECUTABLES: tuple[str, ...] = ("fault_plane", "deform", "tsunami")


@dataclass(frozen=True)
class RuntimePaths:
    model_dir: Path
    tools_dir: Path | None

    @classmethod
    def from_env(cls) -> RuntimePaths:
        return cls(model_dir=model_dir_from_env(), tools_dir=tools_dir_from_env())

    @classmethod
    def resolve(
        cls,
        model_dir: Path | None = None,
        tools_dir: Path | None = None,
        *,
        require_tools: bool = True,
        required_tools: tuple[str, ...] | None = None,
    ) -> RuntimePaths:
        resolved_tools_dir = None
        if require_tools:
            tools_path = (
                tools_dir.resolve() if tools_dir is not None else _tools_dir_env_path()
            )
            resolved_tools_dir = validate_tools_dir(
                tools_path,
                required_tools=required_tools,
            )
        return cls(
            model_dir=validate_model_dir(
                model_dir.resolve() if model_dir is not None else model_dir_from_env()
            ),
            tools_dir=resolved_tools_dir,
        )


def model_dir_from_env() -> Path:
    value = os.environ.get("TSDHN_MODEL_DIR")
    if not value:
        raise RuntimeError("TSDHN_MODEL_DIR must be set to the model asset directory.")
    return validate_model_dir(Path(value).resolve())


def tools_dir_from_env() -> Path:
    return validate_tools_dir(_tools_dir_env_path())


def _tools_dir_env_path() -> Path:
    value = os.environ.get("TSDHN_TOOLS_DIR")
    if not value:
        raise RuntimeError(
            "TSDHN_TOOLS_DIR must be set to the prebuilt model executable directory."
        )
    return Path(value).resolve()


def validate_model_dir(path: Path) -> Path:
    missing_dirs = [
        dirname for dirname in REQUIRED_MODEL_DIRS if not (path / dirname).is_dir()
    ]
    missing_files = [
        filename for filename in REQUIRED_MODEL_FILES if not (path / filename).is_file()
    ]
    if missing_dirs or missing_files:
        missing = [f"{dirname}/" for dirname in missing_dirs] + missing_files
        raise RuntimeError(
            f"Invalid TSDHN model directory '{path}'. Missing: {', '.join(missing)}"
        )
    return path


def validate_tools_dir(
    path: Path, *, required_tools: tuple[str, ...] | None = None
) -> Path:
    required = required_tools or REQUIRED_TOOL_EXECUTABLES
    missing = [
        executable for executable in required if not (path / executable).is_file()
    ]
    if missing:
        raise RuntimeError(
            f"Invalid TSDHN tools directory '{path}'. Missing: {', '.join(missing)}"
        )
    return path
