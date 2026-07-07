import logging
import shutil
import uuid
from datetime import datetime
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from api.core.procrastinate_app import app
from api.core.settings import (
    COMPUTE_DATABASE_URL,
    JOBS_DIR,
    PROCRASTINATE_QUEUE,
)
from api.core.storage import artifact_store, iso
from tsdhn.domain import EarthquakeInput, JobStatus
from tsdhn.engine import SimulationResult, run_simulation
from tsdhn.utils.file_utils import sanitize_for_log

__all__ = [
    "ComputeJobs",
    "JobStatus",
    "compute_jobs",
    "install_compute_schema",
    "run_simulation_task",
]

logger = logging.getLogger(__name__)

JobRow = dict[str, Any]
DB_CONNECT_TIMEOUT_SECONDS = 2


COMPUTE_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS compute_jobs (
  id uuid PRIMARY KEY,
  external_id uuid UNIQUE NOT NULL,
  status text NOT NULL,
  input_params jsonb NOT NULL,
  details text,
  step text,
  step_index integer,
  total_steps integer,
  calculation jsonb,
  travel_times jsonb,
  result_bucket text,
  result_key text,
  error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS compute_jobs_status_idx
  ON compute_jobs(status);

CREATE INDEX IF NOT EXISTS compute_jobs_created_at_idx
  ON compute_jobs(created_at DESC);
"""


SELECT_BY_EXTERNAL_ID = """
SELECT id, external_id, status, input_params, details, step,
       step_index, total_steps, calculation, travel_times, result_bucket,
       result_key, error, created_at, updated_at, started_at, finished_at
FROM compute_jobs
WHERE external_id = %s
"""


SELECT_BY_ID = """
SELECT id, external_id, status, input_params, details, step,
       step_index, total_steps, calculation, travel_times, result_bucket,
       result_key, error, created_at, updated_at, started_at, finished_at
FROM compute_jobs
WHERE id = %s
"""


INSERT_JOB_SQL = """
INSERT INTO compute_jobs (
  id, external_id, status, input_params, details
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (external_id) DO NOTHING
RETURNING id, external_id, status, input_params, details, step,
          step_index, total_steps, calculation, travel_times, result_bucket,
          result_key, error, created_at, updated_at, started_at, finished_at
"""


def install_compute_schema() -> None:
    with psycopg.connect(
        COMPUTE_DATABASE_URL, connect_timeout=DB_CONNECT_TIMEOUT_SECONDS
    ) as conn:
        conn.execute(COMPUTE_JOBS_SCHEMA)
        conn.commit()


def _model_dump(data: EarthquakeInput) -> dict[str, Any]:
    dumped: object = data.model_dump(mode="json")
    if not isinstance(dumped, dict):
        raise TypeError("EarthquakeInput did not dump to a JSON object")
    return cast(dict[str, Any], dumped)


def _as_uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value, version=4)


def _fetch_by_external_id(
    conn: psycopg.Connection[JobRow], external_id: uuid.UUID
) -> JobRow | None:
    row = conn.execute(SELECT_BY_EXTERNAL_ID, [external_id]).fetchone()
    return row


def _fetch_by_id(conn: psycopg.Connection[JobRow], job_id: uuid.UUID) -> JobRow | None:
    row = conn.execute(SELECT_BY_ID, [job_id]).fetchone()
    return row


def _status_from_row(row: JobRow) -> dict[str, Any]:
    status = str(row["status"])
    return {
        "compute_job_id": str(row["id"]),
        "status": status,
        "details": row["details"],
        "step": row["step"],
        "step_index": row["step_index"],
        "total_steps": row["total_steps"],
        "calculation": row["calculation"],
        "travel_times": row["travel_times"],
        "result_bucket": row["result_bucket"],
        "result_key": row["result_key"],
        "error": row["error"],
        "created_at": iso(row["created_at"]),
        "started_at": iso(row["started_at"]),
        "finished_at": iso(row["finished_at"]),
        "artifacts_available": status == JobStatus.COMPLETED.value
        and row["result_key"] is not None,
    }


def _progress_update(
    conn: psycopg.Connection[JobRow],
    compute_job_id: uuid.UUID,
    *,
    details: str,
    values: dict[str, Any] | None = None,
) -> None:
    values = values or {}
    conn.execute(
        """
        UPDATE compute_jobs
        SET status = %s,
            details = %s,
            step = COALESCE(%s, step),
            step_index = COALESCE(%s, step_index),
            total_steps = COALESCE(%s, total_steps),
            calculation = COALESCE(%s, calculation),
            travel_times = COALESCE(%s, travel_times),
            updated_at = now()
        WHERE id = %s
        """,
        [
            JobStatus.RUNNING.value,
            details,
            values.get("step"),
            values.get("step_index"),
            values.get("total_steps"),
            Jsonb(values["calculation"]) if "calculation" in values else None,
            Jsonb(values["travel_times"]) if "travel_times" in values else None,
            compute_job_id,
        ],
    )
    conn.commit()


class ComputeJobs:
    def create_or_get_job(
        self,
        *,
        data: EarthquakeInput,
        external_id: str,
    ) -> dict[str, Any]:
        app_job_id = _as_uuid(external_id)
        input_params = _model_dump(data)

        with (
            psycopg.connect(
                COMPUTE_DATABASE_URL,
                connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
                row_factory=dict_row,
            ) as conn,
            conn.transaction(),
        ):
            compute_job_id = uuid.uuid4()
            inserted = conn.execute(
                INSERT_JOB_SQL,
                [
                    compute_job_id,
                    app_job_id,
                    JobStatus.QUEUED.value,
                    Jsonb(input_params),
                    "Queued for simulation worker",
                ],
            ).fetchone()

            if inserted is None:
                existing = _fetch_by_external_id(conn, app_job_id)
                if existing is None:
                    raise RuntimeError("Compute job was not persisted")
                if existing["input_params"] != input_params:
                    raise ValueError("Job id already exists with different input")
                return _status_from_row(existing)

            run_simulation_task.configure(
                connection=conn,
                queue=PROCRASTINATE_QUEUE,
                queueing_lock=f"simulation:{app_job_id}",
            ).defer(compute_job_id=str(compute_job_id))

            return _status_from_row(inserted)

    def get_job_status(self, app_job_id: str) -> dict[str, Any]:
        try:
            external_id = _as_uuid(app_job_id)
            with psycopg.connect(
                COMPUTE_DATABASE_URL,
                connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
                row_factory=dict_row,
            ) as conn:
                row = _fetch_by_external_id(conn, external_id)
        except Exception as e:
            logger.error(
                "Job lookup failed for %s: %s",
                sanitize_for_log(app_job_id),
                e,
            )
            raise ValueError("Invalid or unknown job ID") from e

        if row is None:
            raise ValueError("Invalid or unknown job ID")
        return _status_from_row(row)

    def is_database_connected(self) -> bool:
        try:
            with psycopg.connect(
                COMPUTE_DATABASE_URL, connect_timeout=DB_CONNECT_TIMEOUT_SECONDS
            ) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def is_storage_connected(self) -> bool:
        return artifact_store.is_connected()


@app.task(
    name="api.run_simulation",
    queue=PROCRASTINATE_QUEUE,
    retry=False,
)
def run_simulation_task(compute_job_id: str) -> None:
    job_uuid = _as_uuid(compute_job_id)

    with psycopg.connect(
        COMPUTE_DATABASE_URL,
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
        row_factory=dict_row,
    ) as conn:
        row = _fetch_by_id(conn, job_uuid)
        if row is None:
            raise RuntimeError(f"Unknown compute job {compute_job_id}")

        app_job_id = str(row["external_id"])
        work_dir = JOBS_DIR / app_job_id
        data = EarthquakeInput(**row["input_params"])

        conn.execute(
            """
            UPDATE compute_jobs
            SET status = %s,
                details = %s,
                started_at = COALESCE(started_at, now()),
                updated_at = now()
            WHERE id = %s
            """,
            [JobStatus.RUNNING.value, "Simulation worker started", job_uuid],
        )
        conn.commit()
        row = _fetch_by_id(conn, job_uuid)
        if row is None:
            raise RuntimeError(f"Unknown compute job {compute_job_id}")

        def on_progress(message: str, details: dict[str, Any]) -> None:
            _progress_update(conn, job_uuid, details=message, values=details)

        try:
            result = run_simulation(
                data,
                work_dir,
                on_progress=on_progress,
            )
            _complete_job(conn, row, result)
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception as e:
            logger.exception("Pipeline failed for job %s", compute_job_id)
            conn.execute(
                """
                UPDATE compute_jobs
                SET status = %s,
                    details = %s,
                    error = %s,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = %s
                """,
                [
                    JobStatus.FAILED.value,
                    "Pipeline failed - check error logs",
                    f"{type(e).__name__}: {e!s}",
                    job_uuid,
                ],
            )
            conn.commit()
            raise


def _complete_job(
    conn: psycopg.Connection[JobRow],
    row: JobRow,
    result: SimulationResult,
) -> None:
    now = datetime.now().astimezone()
    app_job_id = str(row["external_id"])
    compute_job_id = str(row["id"])
    calculation = result.calculation.model_dump(mode="json")
    travel_times = result.travel_times.model_dump(mode="json")

    metadata = {
        "app_job_id": app_job_id,
        "compute_job_id": compute_job_id,
        "status": JobStatus.COMPLETED.value,
        "created_at": iso(row["created_at"]),
        "started_at": iso(row["started_at"]),
        "finished_at": now.isoformat(),
        "calculation": calculation,
        "travel_times": travel_times,
        "artifacts": [
            {
                "name": artifact.name,
                "key": f"simulations/{app_job_id}/artifacts/{artifact.path.name}",
                "content_type": artifact.content_type,
            }
            for artifact in result.bundle.artifacts
        ],
    }
    bucket, metadata_key = artifact_store.upload_simulation_result(
        app_job_id=app_job_id,
        compute_job_id=compute_job_id,
        bundle=result.bundle,
        metadata=metadata,
    )

    conn.execute(
        """
        UPDATE compute_jobs
        SET status = %s,
            details = %s,
            calculation = %s,
            travel_times = %s,
            result_bucket = %s,
            result_key = %s,
            error = NULL,
            finished_at = %s,
            updated_at = now()
        WHERE id = %s
        """,
        [
            JobStatus.COMPLETED.value,
            "Simulation completed successfully",
            Jsonb(calculation),
            Jsonb(travel_times),
            bucket,
            metadata_key,
            now,
            row["id"],
        ],
    )
    conn.commit()


compute_jobs = ComputeJobs()
