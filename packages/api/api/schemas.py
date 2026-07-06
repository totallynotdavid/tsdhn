from pydantic import BaseModel, Field

from core.schemas import CalculationResponse, EarthquakeInput, TsunamiTravelResponse

__all__ = [
    "CalculationPreview",
    "HealthStatus",
    "SimulationCreated",
    "SimulationRequest",
    "SimulationStatus",
    "VersionInfo",
]


class CalculationPreview(BaseModel):
    """Preview data returned before committing to a queued simulation."""

    calculation: CalculationResponse
    travel_times: TsunamiTravelResponse


class SimulationRequest(BaseModel):
    input: EarthquakeInput
    skip_steps: list[str] = Field(default_factory=list)


class SimulationCreated(BaseModel):
    id: str


class SimulationStatus(BaseModel):
    id: str
    status: str
    details: str | None = None
    step: str | None = None
    step_index: int | None = None
    total_steps: int | None = None
    calculation: CalculationResponse | None = None
    travel_times: TsunamiTravelResponse | None = None
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    report_available: bool = False


class HealthStatus(BaseModel):
    status: str
    timestamp: str
    redis_connected: bool


class VersionInfo(BaseModel):
    name: str
    version: str
