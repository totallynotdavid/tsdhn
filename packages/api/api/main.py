import logging
import os
from datetime import datetime
from typing import Any

import anyio
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.core.config import LOGGING_CONFIG
from api.core.queue import JobStatus, tsdhn_queue
from api.models.schemas import EarthquakeInput
from api.utils.job_validators import (
    sanitize_for_log,
    secure_path_construction,
    validate_job_id,
)

logging.basicConfig(**LOGGING_CONFIG)
logger = logging.getLogger(__name__)

app = FastAPI(title="TSDHN API", version="0.1.0", docs_url="/api-docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Limit to specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.post("/run-simulation", status_code=status.HTTP_201_CREATED)
async def run_simulation(
    data: EarthquakeInput, skip_steps: list[str] | None = None
) -> dict[str, Any]:
    """Initialize complete simulation pipeline

    Parameters:
        data: Earthquake parameters for the simulation
        skip_steps: Optional list of processing step names to skip during simulation
    """
    try:
        logger.info("Enqueueing new simulation job")
        job_id = tsdhn_queue.enqueue_job(data=data, skip_steps=skip_steps)
        return {"job_id": job_id}
    except Exception as e:
        logger.exception("Job queuing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start simulation pipeline",
        ) from e


@app.get("/job-status/{job_id}", response_model=dict)
async def get_job_status(job_id: str) -> dict[str, Any]:
    try:
        return tsdhn_queue.get_job_status(job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Status check failed for {sanitize_for_log(job_id)}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job status retrieval failed",
        ) from e


@app.get("/job-result/{job_id}", response_class=FileResponse)
async def get_job_result(job_id: str) -> FileResponse:
    """Retrieve final simulation report"""
    validate_job_id(job_id)

    try:
        job_status = tsdhn_queue.get_job_status(job_id)
        if job_status["status"] != JobStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_425_TOO_EARLY,
                detail="Job processing not complete",
            )

        job_dir = secure_path_construction(job_id)
        report_path = job_dir / "reporte.pdf"

        if not await anyio.to_thread.run_sync(report_path.exists):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not generated"
            )

        return FileResponse(
            report_path,
            filename=f"tsdhn_report_{job_id}.pdf",
            media_type="application/pdf",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Result retrieval failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Result retrieval error",
        ) from e


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "redis_connected": tsdhn_queue.is_redis_connected(),
    }


def start_app() -> None:
    # Default binds to loopback; set APP_HOST=0.0.0.0 in containers.
    uvicorn.run(
        app,
        host=os.environ.get("APP_HOST", "127.0.0.1"),
        port=int(os.environ.get("APP_PORT", "8000")),
        log_level="info",
    )


if __name__ == "__main__":
    start_app()
