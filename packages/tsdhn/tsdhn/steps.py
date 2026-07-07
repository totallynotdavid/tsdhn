import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tsdhn.render.maxola import generate_maxola_plot
from tsdhn.render.point_ttt import generate_ttt_map
from tsdhn.render.ttt_inverso import ttt_inverso_python
from tsdhn.render.ttt_max import process_tsunami_data

__all__ = [
    "EARTH_RADIUS",
    "GRAVITY",
    "MASTER_PIPELINE",
    "PROCESSING_PIPELINE",
    "REPORT_STEPS",
    "TTT_MUNDO_STEPS",
    "ProcessingStep",
]


GRAVITY: float = 9.81  # m/s2
EARTH_RADIUS: float = 6370.8  # km


@dataclass(frozen=True)
class ProcessingStep:
    name: str
    outputs: tuple[str, ...]
    command: list[str] | None = None
    python_callable: Callable[[Path], Path | str | None] | None = None
    system_executables: tuple[str, ...] = ()
    file_checks: list[tuple[str, str]] = field(default_factory=list)
    working_dir: str | None = None

    def __post_init__(self) -> None:
        if not (self.command is None) ^ (self.python_callable is None):
            raise ValueError(
                "ProcessingStep must have either command or python_callable"
            )


def copy_ttt_pdf(working_dir: Path) -> None:
    shutil.copy(working_dir / "ttt.pdf", working_dir.parent / "ttt.pdf")


PROCESSING_PIPELINE = (
    ProcessingStep(
        name="fault_plane",
        outputs=("pfalla.inp",),
        command=["./fault_plane"],
        file_checks=[("pfalla.inp", "Input file for deform not generated")],
    ),
    ProcessingStep(
        name="deform",
        outputs=("deform",),
        command=["./deform"],
        file_checks=[("deform", "Deform executable missing")],
    ),
    ProcessingStep(
        name="tsunami",
        outputs=("zfolder/green.dat", "zfolder/zmax_a.grd"),
        command=["./tsunami"],
        file_checks=[
            ("zfolder/green.dat", "Green data file missing"),
            ("zfolder/zmax_a.grd", "Zmax grid file missing"),
        ],
    ),
    ProcessingStep(
        name="maxola",
        outputs=("maxola.pdf",),
        python_callable=generate_maxola_plot,
        system_executables=("gmt",),
        file_checks=[("maxola.pdf", "Maxola output missing")],
    ),
    ProcessingStep(
        name="ttt_max",
        outputs=("zfolder/green_rev.dat", "ttt_max.dat", "mareograma.svg"),
        python_callable=process_tsunami_data,
        file_checks=[
            ("zfolder/green_rev.dat", "Scaled wave height data output missing"),
            ("ttt_max.dat", "TTT Max data output missing"),
            ("mareograma.svg", "Mareogram plot missing"),
        ],
    ),
)

TTT_MUNDO_STEPS = (
    ProcessingStep(
        name="ttt_inverso",
        outputs=("ttt_mundo/ttt.b",),
        python_callable=ttt_inverso_python,
        system_executables=("gmt", "ttt_client"),
        working_dir="ttt_mundo",
        file_checks=[("ttt.b", "ttt_client output missing")],
    ),
    ProcessingStep(
        name="point_ttt",
        outputs=("ttt_mundo/ttt.pdf",),
        python_callable=generate_ttt_map,
        system_executables=("gmt",),
        working_dir="ttt_mundo",
        file_checks=[("ttt.pdf", "ttt.pdf not generated")],
    ),
    ProcessingStep(
        name="copy_ttt_pdf",
        outputs=("ttt.pdf",),
        python_callable=copy_ttt_pdf,
        working_dir="ttt_mundo",
        file_checks=[("../ttt.pdf", "ttt.pdf not copied to parent directory")],
    ),
)

REPORT_STEPS: tuple[ProcessingStep, ...] = ()

MASTER_PIPELINE = PROCESSING_PIPELINE + TTT_MUNDO_STEPS
