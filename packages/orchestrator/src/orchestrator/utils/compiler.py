import subprocess
from pathlib import Path

from orchestrator.core.config import CompilerConfig
from orchestrator.core.executables import resolve


def compile_fortran(working_dir: Path, config: CompilerConfig) -> None:
    # `config.compiler` is a frozen `CompilerConfig` field, not user input.
    compiler = str(resolve(config.compiler))
    args = [compiler, *config.flags, config.source, "-o", config.output]
    subprocess.run(args, cwd=working_dir, check=True)
