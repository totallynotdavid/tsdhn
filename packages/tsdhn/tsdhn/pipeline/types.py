import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tsdhn.utils.file_utils import make_executable

type StepFunction = Callable[[Path], None]
type FileCheck = tuple[str, str]


@dataclass(frozen=True)
class PythonRunner:
    fn: StepFunction

    def run(self, working_dir: Path, tools_dir: Path | None) -> None:
        self.fn(working_dir)


@dataclass(frozen=True)
class ToolRunner:
    executable: str
    args: tuple[str, ...] = ()

    def run(self, working_dir: Path, tools_dir: Path | None) -> None:
        if tools_dir is None:
            raise RuntimeError(
                f"Tool step '{self.executable}' requires TSDHN_TOOLS_DIR with "
                "prebuilt executables."
            )

        source = tools_dir / self.executable
        if not source.is_file():
            raise FileNotFoundError(f"Required model executable missing: {source}")

        target = working_dir / self.executable
        shutil.copy2(source, target)
        make_executable(target)
        subprocess.run(
            [f"./{self.executable}", *self.args],
            cwd=working_dir,
            check=True,
        )


type StepRunner = PythonRunner | ToolRunner


@dataclass(frozen=True)
class ProcessingStep:
    name: str
    outputs: tuple[str, ...]
    runner: StepRunner
    required_system_executables: tuple[str, ...] = ()
    file_checks: tuple[FileCheck, ...] = ()
    working_dir: str | None = None
