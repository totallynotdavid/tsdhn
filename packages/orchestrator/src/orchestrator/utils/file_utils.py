import shutil
from pathlib import Path


def make_executable(file_path: Path) -> None:
    file_path.chmod(file_path.stat().st_mode | 0o111)


def validate_files(cwd: Path, checks: list[tuple[str, str]]) -> None:
    missing = []
    for filename, msg in checks:
        if not (cwd / filename).exists():
            missing.append(f"{filename}: {msg}")
    if missing:
        raise FileNotFoundError("\n".join(missing))


def setup_workspace(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def sanitize_for_log(value: str) -> str:
    """
    Sanitize a value for logging to prevent log injection attacks.
    Replaces newlines and control characters that could be used for log forging.
    """
    if value is None:
        return "None"

    value_str = str(value)  # Force it to be a string

    sanitized = value_str.replace("\n", "\\n").replace("\r", "\\r")

    # Avoid huge log entries
    max_length = 100
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."

    return sanitized
