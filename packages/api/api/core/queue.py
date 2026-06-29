import logging
import shutil
import uuid
from typing import Any

from redis import Redis
from rq import Queue, get_current_job
from rq.job import Job

from api.core.calculator import TsunamiCalculator
from api.core.config import MASTER_PIPELINE, MODEL_DIR, REPO_ROOT
from api.core.executables import ensure_all
from api.models.schemas import EarthquakeInput, JobStatus
from api.utils.file_utils import sanitize_for_log, setup_workspace
from api.utils.processing import process_step

__all__ = ["JobStatus", "TSDHNQueue", "execute_pipeline", "tsdhn_queue"]

logger = logging.getLogger(__name__)


class TSDHNQueue:
    def __init__(self, redis_conn: Redis):
        self.redis = redis_conn
        self.queue = Queue("tsdhn_queue", connection=redis_conn)

    def enqueue_job(
        self, data: EarthquakeInput, skip_steps: list[str] | None = None
    ) -> str | None:
        skip_steps = skip_steps or []
        self._validate_skip_steps(skip_steps)

        try:
            job_id = str(uuid.uuid4())
            self.queue.enqueue(
                execute_pipeline,
                data.model_dump(),
                skip_steps,
                job_id=job_id,
                job_timeout="2h",
                meta={
                    "status": JobStatus.QUEUED.value,
                    "details": "Initializing simulation pipeline",
                    "data": data.model_dump(),
                },
                result_ttl=86400,
            )
            return job_id
        except Exception as e:
            logger.exception("Job enqueue failed")
            raise RuntimeError(f"Failed to enqueue job: {e!s}") from e

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        try:
            job = Job.fetch(job_id, connection=self.redis)
            status_map = {
                "queued": JobStatus.QUEUED.value,
                "started": JobStatus.RUNNING.value,
                "finished": JobStatus.COMPLETED.value,
                "failed": JobStatus.FAILED.value,
            }

            return {
                "status": status_map.get(job.get_status(), JobStatus.QUEUED.value),
                "calculation": job.meta.get("calculation"),
                "travel_times": job.meta.get("travel_times"),
                "details": job.meta.get("details"),
                "error": job.meta.get("error"),
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "ended_at": job.ended_at.isoformat() if job.ended_at else None,
                "download_url": f"/job-result/{job_id}"
                if job.meta.get("status") == JobStatus.COMPLETED.value
                else None,
            }
        except Exception as e:
            logger.error(f"Invalid job ID {sanitize_for_log(job_id)}: {e!s}")
            raise ValueError("Invalid or expired job ID") from e

    def is_redis_connected(self) -> bool:
        try:
            result: Any = self.redis.ping()
            return bool(result)
        except Exception:
            return False

    @staticmethod
    def _validate_skip_steps(skip_steps: list[str]) -> None:
        valid_steps = {step.name for step in MASTER_PIPELINE}
        invalid = set(skip_steps) - valid_steps
        if invalid:
            raise ValueError(f"Invalid steps to skip: {', '.join(invalid)}")


def execute_pipeline(
    data_dict: dict[str, Any], skip_steps: list[str]
) -> dict[str, str]:
    """Main pipeline executor"""
    job = get_current_job()
    if job is None:
        raise RuntimeError("No current job in worker context")
    job_id = job.id
    work_dir = REPO_ROOT / "jobs" / job_id
    data = EarthquakeInput(**data_dict)
    calculator = TsunamiCalculator()

    try:
        setup_workspace(MODEL_DIR, work_dir)

        def update_meta(details: str, **kwargs: Any) -> None:
            job.meta.update({"details": details, **kwargs})
            job.save_meta()  # type: ignore[no-untyped-call]

        # Phase 1: Initial calculations
        update_meta("Running earthquake calculations")
        calc_result = calculator.calculate_earthquake_parameters(data, work_dir)
        update_meta(
            "Earthquake calculations complete",
            calculation=calc_result.dict(),
            status=JobStatus.RUNNING.value,
        )

        # Phase 2: Tsunami travel times
        update_meta("Calculating tsunami travel times")
        tsunami_result = calculator.calculate_tsunami_travel_times(data)
        update_meta(
            "Tsunami calculations complete",
            travel_times=tsunami_result.dict(),
            status=JobStatus.RUNNING.value,
        )

        # Phase 3: Main simulation pipeline
        ensure_all()
        for step in MASTER_PIPELINE:
            if step.name in skip_steps:
                logger.info(f"Skipping step: {step.name}")
                continue

            update_meta(f"Processing {step.name}")
            step_dir = work_dir / step.working_dir if step.working_dir else work_dir
            step_dir.mkdir(parents=True, exist_ok=True)
            process_step(step, step_dir)

        update_meta(
            "Simulation completed successfully",
            status=JobStatus.COMPLETED.value,
            download_url=f"/job-result/{job_id}",
        )
        return {"status": "completed"}

    except Exception as e:
        logger.exception(f"Pipeline failed for job {job_id}")
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
        if job is not None:
            job.meta.update(
                {
                    "status": JobStatus.FAILED.value,
                    "error": f"{type(e).__name__}: {e!s}",
                    "details": "Pipeline failed - check error logs",
                }
            )
            job.save_meta()  # type: ignore[no-untyped-call]
        raise


tsdhn_queue = TSDHNQueue(Redis(host="localhost", port=6379, db=0))
