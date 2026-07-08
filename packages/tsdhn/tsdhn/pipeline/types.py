from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

type StepFunction = Callable[[Path], None]
type FileCheck = tuple[str, str]


@dataclass(frozen=True)
class PythonRunner:
    fn: StepFunction


@dataclass(frozen=True)
class ToolRunner:
    executable: str
    args: tuple[str, ...] = ()


type StepRunner = PythonRunner | ToolRunner


@dataclass(frozen=True)
class ProcessingStep:
    name: str
    outputs: tuple[str, ...]
    runner: StepRunner
    required_system_executables: tuple[str, ...] = ()
    file_checks: tuple[FileCheck, ...] = ()
    working_dir: str | None = None
