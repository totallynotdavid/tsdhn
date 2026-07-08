import shutil
from pathlib import Path


def copy_ttt_pdf(working_dir: Path) -> None:
    shutil.copy(working_dir / "ttt.pdf", working_dir.parent / "ttt.pdf")
