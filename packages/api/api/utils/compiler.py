import subprocess
from pathlib import Path

from api.core.config import CompilerConfig
from api.core.executables import resolve

__all__ = ["compile_fortran"]


def compile_fortran(working_dir: Path, config: CompilerConfig) -> None:
    # `config.compiler` is a frozen `CompilerConfig` field, not user input.
    compiler = str(resolve(config.compiler))
    args = [compiler, *config.flags, config.source, "-o", config.output]
    subprocess.run(args, cwd=working_dir, check=True)
