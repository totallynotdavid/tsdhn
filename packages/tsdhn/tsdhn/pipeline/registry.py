from tsdhn.pipeline.types import ProcessingStep, PythonRunner, ToolRunner
from tsdhn.render.copy import copy_ttt_pdf
from tsdhn.render.maxola import generate_maxola_plot
from tsdhn.render.point_ttt import generate_ttt_map
from tsdhn.render.ttt_inverso import ttt_inverso_python
from tsdhn.render.ttt_max import process_tsunami_data

__all__ = [
    "DEFAULT_PIPELINE",
    "PROCESSING_PIPELINE",
    "REPORT_PIPELINE",
    "TTT_MUNDO_PIPELINE",
]


PROCESSING_PIPELINE: tuple[ProcessingStep, ...] = (
    ProcessingStep(
        name="fault_plane",
        outputs=("pfalla.inp",),
        runner=ToolRunner("fault_plane"),
        file_checks=(("pfalla.inp", "Input file for deform not generated"),),
    ),
    ProcessingStep(
        name="deform",
        outputs=("deform",),
        runner=ToolRunner("deform"),
        file_checks=(("deform", "Deform executable missing"),),
    ),
    ProcessingStep(
        name="tsunami",
        outputs=("zfolder/green.dat", "zfolder/zmax_a.grd"),
        runner=ToolRunner("tsunami"),
        file_checks=(
            ("zfolder/green.dat", "Green data file missing"),
            ("zfolder/zmax_a.grd", "Zmax grid file missing"),
        ),
    ),
    ProcessingStep(
        name="maxola",
        outputs=("maxola.pdf",),
        runner=PythonRunner(generate_maxola_plot),
        required_system_executables=("gmt",),
        file_checks=(("maxola.pdf", "Maxola output missing"),),
    ),
    ProcessingStep(
        name="ttt_max",
        outputs=("zfolder/green_rev.dat", "ttt_max.dat", "mareograma.svg"),
        runner=PythonRunner(process_tsunami_data),
        file_checks=(
            ("zfolder/green_rev.dat", "Scaled wave height data output missing"),
            ("ttt_max.dat", "TTT Max data output missing"),
            ("mareograma.svg", "Mareogram plot missing"),
        ),
    ),
)

TTT_MUNDO_PIPELINE: tuple[ProcessingStep, ...] = (
    ProcessingStep(
        name="ttt_inverso",
        outputs=("ttt_mundo/ttt.b",),
        runner=PythonRunner(ttt_inverso_python),
        required_system_executables=("gmt", "ttt_client"),
        working_dir="ttt_mundo",
        file_checks=(("ttt.b", "ttt_client output missing"),),
    ),
    ProcessingStep(
        name="point_ttt",
        outputs=("ttt_mundo/ttt.pdf",),
        runner=PythonRunner(generate_ttt_map),
        required_system_executables=("gmt",),
        working_dir="ttt_mundo",
        file_checks=(("ttt.pdf", "ttt.pdf not generated"),),
    ),
    ProcessingStep(
        name="copy_ttt_pdf",
        outputs=("ttt.pdf",),
        runner=PythonRunner(copy_ttt_pdf),
        working_dir="ttt_mundo",
        file_checks=(("../ttt.pdf", "ttt.pdf not copied to parent directory"),),
    ),
)

REPORT_PIPELINE: tuple[ProcessingStep, ...] = ()

DEFAULT_PIPELINE: tuple[ProcessingStep, ...] = PROCESSING_PIPELINE + TTT_MUNDO_PIPELINE
