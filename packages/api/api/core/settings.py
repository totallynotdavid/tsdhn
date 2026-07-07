import os
from pathlib import Path

__all__ = [
    "COMPUTE_DATABASE_URL",
    "JOBS_DIR",
    "MINIO_ACCESS_KEY",
    "MINIO_BUCKET",
    "MINIO_ENDPOINT",
    "MINIO_SECRET_KEY",
    "MINIO_SECURE",
    "PROCRASTINATE_QUEUE",
    "REPORT_DOWNLOAD_MAX_BYTES",
]

COMPUTE_DATABASE_URL = os.environ.get(
    "COMPUTE_DATABASE_URL",
    "postgresql://tsdhn:tsdhn@localhost:5432/tsdhn_compute",
)

PROCRASTINATE_QUEUE = os.environ.get("PROCRASTINATE_QUEUE", "simulations")

JOBS_DIR: Path = Path(os.environ.get("TSDHN_JOBS_DIR", "jobs")).resolve()

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "tsdhn-results")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() in {
    "1",
    "true",
    "yes",
}
REPORT_DOWNLOAD_MAX_BYTES = int(
    os.environ.get("REPORT_DOWNLOAD_MAX_BYTES", str(50 * 1024 * 1024))
)
