import shutil
from pathlib import Path
from typing import Any

from orchestrator.models.schemas import CompilerConfig, ProcessingStep
from orchestrator.modules.maxola import generate_maxola_plot
from orchestrator.modules.point_ttt import generate_ttt_map
from orchestrator.modules.reporte import generate_reports_wrapper
from orchestrator.modules.ttt_inverso import ttt_inverso_python
from orchestrator.modules.ttt_max import process_tsunami_data

# Resolve repo root from this file's location.
# Layout: <repo>/packages/orchestrator/src/orchestrator/core/config.py
_REPO_ROOT: Path = Path(__file__).resolve().parents[4]

# Constants
GRAVITY: float = 9.81  # m/s²
EARTH_RADIUS: float = 6370.8  # km
MODEL_DIR: Path = _REPO_ROOT / "model"
REPO_ROOT: Path = _REPO_ROOT

# Logging configuration
LOGGING_CONFIG: dict[str, Any] = {
    "filename": "tsunami_api.log",
    "level": "DEBUG",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
}

# Processing Pipelines
PROCESSING_PIPELINE = [
    ProcessingStep(
        name="fault_plane",
        command=["./fault_plane"],
        file_checks=[("pfalla.inp", "Input file for deform not generated")],
        compiler_config=CompilerConfig(
            source="fault_plane.f90",
            output="fault_plane",
            compiler="ifx",
            flags=["-parallel"],
        ),
    ),
    ProcessingStep(
        name="deform",
        command=["./deform"],
        file_checks=[("deform", "Deform executable missing")],
        compiler_config=CompilerConfig(
            source="def_oka.f",
            output="deform",
            compiler="ifx",
            flags=["-parallel"],
        ),
    ),
    ProcessingStep(
        name="tsunami",
        command=["./tsunami"],
        file_checks=[
            ("zfolder/green.dat", "Green data file missing"),
            ("zfolder/zmax_a.grd", "Zmax grid file missing"),
        ],
        compiler_config=CompilerConfig(
            source="tsunami1.for",
            output="tsunami",
            compiler="ifx",
            flags=["-parallel", "-qopenmp"],
        ),
    ),
    ProcessingStep(
        name="maxola",
        python_callable=generate_maxola_plot,
        file_checks=[("maxola.eps", "Maxola output missing")],
    ),
    ProcessingStep(
        name="ttt_max",
        python_callable=process_tsunami_data,
        file_checks=[
            ("zfolder/green_rev.dat", "Scaled wave height data output missing"),
            ("ttt_max.dat", "TTT Max data output missing"),
            ("mareograma.eps", "Mareogram plot missing"),
        ],
    ),
]

TTT_MUNDO_STEPS = [
    ProcessingStep(
        name="ttt_inverso",
        python_callable=ttt_inverso_python,
        working_dir="ttt_mundo",
        file_checks=[("ttt.b", "ttt_client output missing")],
    ),
    ProcessingStep(
        name="point_ttt",
        python_callable=generate_ttt_map,
        working_dir="ttt_mundo",
        extra_executables=["point_ttt"],
        file_checks=[("ttt.eps", "ttt.eps not generated")],
    ),
    ProcessingStep(
        name="copy_ttt_eps",
        python_callable=lambda wd: shutil.copy(wd / "ttt.eps", wd.parent / "ttt.eps"),
        working_dir="ttt_mundo",
        file_checks=[("../ttt.eps", "ttt.eps not copied to parent directory")],
    ),
]

REPORT_STEPS = [
    ProcessingStep(
        name="generate_reports",
        python_callable=generate_reports_wrapper,
        file_checks=[("reporte.pdf", "Final report PDF missing")],
    ),
]

MASTER_PIPELINE = PROCESSING_PIPELINE + TTT_MUNDO_STEPS + REPORT_STEPS
