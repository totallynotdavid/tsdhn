import logging
import os
import uuid
from pathlib import Path

from fastapi import HTTPException

from api.core.queue import JOBS_DIR, tsdhn_queue
from core.utils.file_utils import sanitize_for_log

__all__ = ["sanitize_for_log", "secure_path_construction", "validate_job_id"]

logger = logging.getLogger(__name__)


def validate_job_id(job_id: str) -> None:
    """Reject malformed ids before looking up queue state."""
    try:
        uuid.UUID(job_id, version=4)
    except ValueError as e:
        logger.warning("Invalid job ID format: %s", sanitize_for_log(job_id))
        raise HTTPException(status_code=400, detail="Invalid job identifier") from e

    try:
        tsdhn_queue.get_job_status(job_id)
    except ValueError as e:
        logger.warning("Invalid job not found: %s", sanitize_for_log(job_id))
        raise HTTPException(status_code=404, detail="Job not found") from e


def secure_path_construction(job_id: str) -> Path:
    base_dir = JOBS_DIR.resolve()
    base_str = str(base_dir)

    constructed_path = os.path.join(base_str, job_id)
    normalized_path = os.path.normpath(constructed_path)

    if not normalized_path.startswith(base_str):
        logger.error("Path traversal attempt detected: %s", sanitize_for_log(job_id))
        raise HTTPException(status_code=400, detail="Invalid job path")

    job_dir = Path(normalized_path).resolve()

    # Symlinks must not escape the jobs directory.
    if not job_dir.is_relative_to(base_dir):
        logger.error("Resolved path traversal detected: %s", sanitize_for_log(job_id))
        raise HTTPException(status_code=400, detail="Invalid job path")

    return job_dir
