import shutil
from pathlib import Path

WORKSPACE_DIRS: tuple[str, ...] = ("bathy", "ttt_mundo", "zfolder")
WORKSPACE_INPUTS: tuple[str, ...] = (
    "mecfoc.dat",
    "tidal.dat",
    "bathy/grid_a.grd",
    "bathy/xa.dat",
    "bathy/ya.dat",
    "ttt_mundo/cortado.i2",
)


def make_executable(file_path: Path) -> None:
    file_path.chmod(file_path.stat().st_mode | 0o111)


def validate_files(cwd: Path, checks: list[tuple[str, str]]) -> None:
    missing = []
    for filename, msg in checks:
        if not (cwd / filename).exists():
            missing.append(f"{filename}: {msg}")
    if missing:
        raise FileNotFoundError("\n".join(missing))


def prepare_simulation_workspace(model_dir: Path, work_dir: Path) -> None:
    """Create the per-run filesystem expected by the legacy pipeline.

    Only immutable inputs required by the active pipeline are linked/copied into
    the workspace. Generated files are intentionally absent at startup.
    """
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    for dirname in WORKSPACE_DIRS:
        (work_dir / dirname).mkdir()

    for relative_name in WORKSPACE_INPUTS:
        source = model_dir / relative_name
        if not source.is_file():
            raise FileNotFoundError(f"Required model input missing: {source}")
        destination = work_dir / relative_name
        _link_or_copy(source, destination)


def _link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.symlink_to(source)
    except OSError:
        shutil.copy2(source, destination)


def sanitize_for_log(value: str) -> str:
    """Log values cannot contain control characters that could forge entries."""
    if value is None:
        return "None"

    value_str = str(value)

    sanitized = value_str.replace("\n", "\\n").replace("\r", "\\r")

    # Log fields are capped so malicious ids cannot flood API logs.
    max_length = 100
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."

    return sanitized
