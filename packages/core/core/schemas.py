from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, field_validator


class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EarthquakeInput(BaseModel):
    Mw: float
    h: float
    lat0: float
    lon0: float
    dia: str | None = "00"
    hhmm: str | None = "0000"

    @field_validator("lon0")
    @classmethod
    def convert_longitude(cls, v: float) -> float:
        return v - 360 if v > 0 else v

    @field_validator("hhmm")
    @classmethod
    def validate_time(cls, v: str) -> str:
        if len(v) == 0 or len(v) < 4:
            return "0000"
        if ":" in v:
            return v.replace(":", "")
        return v


class CalculationResponse(BaseModel):
    length: float
    width: float
    dislocation: float
    seismic_moment: float
    tsunami_warning: str
    distance_to_coast: float
    azimuth: float
    dip: float
    epicenter_location: str
    rectangle_parameters: dict[str, float]
    rectangle_corners: list[dict[str, float]]


class TsunamiTravelResponse(BaseModel):
    arrival_times: dict[str, str]
    distances: dict[str, float]
    epicenter_info: dict[str, str]


@dataclass(frozen=True)
class ProcessingStep:
    name: str
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
