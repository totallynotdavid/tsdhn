"""
Two routers: `ops_router` is unauthenticated (health/version, for liveness
probes); `router` carries the service-token dependency on every data route.
"""

import json
import logging
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from functools import lru_cache, partial
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api import __version__
from api.core.jobs import (
    JobStatus,
    ReportInvariantError,
    ReportMissingError,
    ReportNotReadyError,
    ReportStorageError,
    ReportTooLargeError,
    compute_jobs,
)
from api.schemas import (
    CalculationPreview,
    HealthStatus,
    JobCreated,
    JobRequest,
    JobStatusResponse,
    VersionInfo,
)
from api.security import require_service_token
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
    tags=["jobs"],
)


@ops_router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    database_connected = await anyio.to_thread.run_sync(
        compute_jobs.is_database_connected
    )
    storage_connected = await anyio.to_thread.run_sync(
        compute_jobs.is_storage_connected
    )
    return HealthStatus(
        status="healthy" if database_connected and storage_connected else "degraded",
        timestamp=datetime.now().isoformat(),
        database_connected=database_connected,
        storage_connected=storage_connected,
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
    "/jobs",
    response_model=JobCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_job(req: JobRequest) -> JobCreated:
    app_job_id = str(req.app_job_id)
    try:
        job_status = await anyio.to_thread.run_sync(
            partial(
                compute_jobs.create_or_get_job,
                data=req.input,
                skip_steps=req.skip_steps,
                external_id=app_job_id,
            )
        )
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

    return JobCreated(app_job_id=app_job_id, **job_status)


@router.get("/jobs/{app_job_id}", response_model=JobStatusResponse)
async def get_job(app_job_id: str) -> JobStatusResponse:
    try:
        job_status = await anyio.to_thread.run_sync(
            compute_jobs.get_job_status, app_job_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return JobStatusResponse(app_job_id=app_job_id, **job_status)


@router.get("/jobs/{app_job_id}/events")
async def job_events(app_job_id: str) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        while True:
            try:
                job_status = await anyio.to_thread.run_sync(
                    compute_jobs.get_job_status, app_job_id
                )
            except ValueError:
                yield f"event: error\ndata: {json.dumps({'error': 'unknown job'})}\n\n"
                return
            yield f"data: {json.dumps({'app_job_id': app_job_id, **job_status})}\n\n"
            if job_status["status"] in _TERMINAL:
                return
            await anyio.sleep(2)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/jobs/{app_job_id}/report")
async def get_job_report(app_job_id: str) -> StreamingResponse:
    try:
        uuid.UUID(app_job_id, version=4)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job identifier"
        ) from e

    try:
        report = await anyio.to_thread.run_sync(
            compute_jobs.get_report_download, app_job_id
        )
    except ReportNotReadyError as e:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Report is not available",
        ) from e
    except ReportMissingError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report was not found",
        ) from e
    except ReportTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Report exceeds the download size limit",
        ) from e
    except ReportStorageError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report storage is unavailable",
        ) from e
    except ReportInvariantError as e:
        logger.exception("Report download invariant failed for job %s", app_job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report metadata is inconsistent",
        ) from e

    return StreamingResponse(
        report.chunks,
        media_type=report.content_type,
        headers={
            "Content-Disposition": 'attachment; filename="reporte.pdf"',
            "Content-Length": str(report.size),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
