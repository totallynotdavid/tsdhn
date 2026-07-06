import shutil

from core.modules.maxola import generate_maxola_plot
from core.modules.point_ttt import generate_ttt_map
from core.modules.reporte import generate_reports_wrapper
from core.modules.ttt_inverso import ttt_inverso_python
from core.modules.ttt_max import process_tsunami_data
from core.schemas import ProcessingStep

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

PROCESSING_PIPELINE = [
    ProcessingStep(
        name="fault_plane",
        command=["./fault_plane"],
        file_checks=[("pfalla.inp", "Input file for deform not generated")],
    ),
    ProcessingStep(
        name="deform",
        command=["./deform"],
        file_checks=[("deform", "Deform executable missing")],
    ),
    ProcessingStep(
        name="tsunami",
        command=["./tsunami"],
        file_checks=[
            ("zfolder/green.dat", "Green data file missing"),
            ("zfolder/zmax_a.grd", "Zmax grid file missing"),
        ],
    ),
    ProcessingStep(
        name="maxola",
        python_callable=generate_maxola_plot,
        system_executables=("gmt",),
        file_checks=[("maxola.svg", "Maxola output missing")],
    ),
    ProcessingStep(
        name="ttt_max",
        python_callable=process_tsunami_data,
        file_checks=[
            ("zfolder/green_rev.dat", "Scaled wave height data output missing"),
            ("ttt_max.dat", "TTT Max data output missing"),
            ("mareograma.svg", "Mareogram plot missing"),
        ],
    ),
]

TTT_MUNDO_STEPS = [
    ProcessingStep(
        name="ttt_inverso",
        python_callable=ttt_inverso_python,
        system_executables=("gmt", "ttt_client"),
        working_dir="ttt_mundo",
        file_checks=[("ttt.b", "ttt_client output missing")],
    ),
    ProcessingStep(
        name="point_ttt",
        python_callable=generate_ttt_map,
        system_executables=("gmt",),
        working_dir="ttt_mundo",
        file_checks=[("ttt.svg", "ttt.svg not generated")],
    ),
    ProcessingStep(
        name="copy_ttt_svg",
        python_callable=lambda wd: shutil.copy(wd / "ttt.svg", wd.parent / "ttt.svg"),
        working_dir="ttt_mundo",
        file_checks=[("../ttt.svg", "ttt.svg not copied to parent directory")],
    ),
]

REPORT_STEPS = [
    ProcessingStep(
        name="generate_reports",
        python_callable=generate_reports_wrapper,
        system_executables=("typst",),
        file_checks=[("reporte.pdf", "Final report PDF missing")],
    ),
]

MASTER_PIPELINE = PROCESSING_PIPELINE + TTT_MUNDO_STEPS + REPORT_STEPS
