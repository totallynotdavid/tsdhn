"""
Two routers: `ops_router` is unauthenticated (health/version, for liveness
probes); `router` carries the service-token dependency on every data route.
"""

import json
import logging
import tempfile
from collections.abc import AsyncIterator
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse

from api import __version__
from api.core.queue import JobStatus, tsdhn_queue
from api.schemas import (
    CalculationPreview,
    HealthStatus,
    SimulationCreated,
    SimulationRequest,
    SimulationStatus,
    VersionInfo,
)
from api.security import require_service_token
from api.utils.job_validators import secure_path_construction, validate_job_id
from core.calculator import TsunamiCalculator
from core.schemas import EarthquakeInput

logger = logging.getLogger(__name__)

_TERMINAL = {JobStatus.COMPLETED.value, JobStatus.FAILED.value}


@lru_cache(maxsize=1)
def get_calculator() -> TsunamiCalculator:
    """Process-wide calculator. Model data loads once."""
    return TsunamiCalculator()


ops_router = APIRouter(prefix="/api/v1", tags=["ops"])
router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_service_token)],
    tags=["simulations"],
)


@ops_router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        redis_connected=tsdhn_queue.is_redis_connected(),
    )


@ops_router.get("/version", response_model=VersionInfo)
async def version() -> VersionInfo:
    return VersionInfo(name="tsdhn-api", version=__version__)


@router.post("/calculations", response_model=CalculationPreview)
async def create_calculation(data: EarthquakeInput) -> CalculationPreview:
    calculator = get_calculator()

    def compute() -> CalculationPreview:
        # The preview writes hypo.dat, but previews must not mutate the workspace.
        with tempfile.TemporaryDirectory() as tmp:
            calculation = calculator.calculate_earthquake_parameters(data, Path(tmp))
        travel_times = calculator.calculate_tsunami_travel_times(data)
        return CalculationPreview(calculation=calculation, travel_times=travel_times)

    return await anyio.to_thread.run_sync(compute)


@router.post(
    "/simulations",
    response_model=SimulationCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulation(req: SimulationRequest) -> SimulationCreated:
    try:
        job_id = tsdhn_queue.enqueue_job(data=req.input, skip_steps=req.skip_steps)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("Job queuing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start simulation pipeline",
        ) from e

    if job_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start simulation pipeline",
        )
    return SimulationCreated(id=job_id)


@router.get("/simulations/{sim_id}", response_model=SimulationStatus)
async def get_simulation(sim_id: str) -> SimulationStatus:
    try:
        job_status = tsdhn_queue.get_job_status(sim_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return SimulationStatus(id=sim_id, **job_status)


@router.get("/simulations/{sim_id}/events")
async def simulation_events(sim_id: str) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        while True:
            try:
                job_status = await anyio.to_thread.run_sync(
                    tsdhn_queue.get_job_status, sim_id
                )
            except ValueError:
                yield f"event: error\ndata: {json.dumps({'error': 'unknown job'})}\n\n"
                return
            yield f"data: {json.dumps(job_status)}\n\n"
            if job_status["status"] in _TERMINAL:
                return
            await anyio.sleep(2)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/simulations/{sim_id}/report", response_class=FileResponse)
async def get_report(sim_id: str) -> FileResponse:
    validate_job_id(sim_id)

    job_status = tsdhn_queue.get_job_status(sim_id)
    if job_status["status"] != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Job processing not complete",
        )

    report_path = secure_path_construction(sim_id) / "reporte.pdf"
    if not await anyio.to_thread.run_sync(report_path.exists):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not generated"
        )

    return FileResponse(
        report_path,
        filename=f"tsdhn_report_{sim_id}.pdf",
        media_type="application/pdf",
    )
