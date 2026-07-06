import json
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import urllib3
from minio import Minio

from api.core.settings import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
)

__all__ = ["ArtifactStore", "artifact_store"]


class ArtifactStore:
    def __init__(self) -> None:
        self.bucket = MINIO_BUCKET
        self._client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
            http_client=urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=2.0, read=2.0),
                retries=False,
            ),
        )

    def is_connected(self) -> bool:
        try:
            self._client.bucket_exists(self.bucket)
            return True
        except Exception:
            return False

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self.bucket):
            self._client.make_bucket(self.bucket)

    def upload_simulation_result(
        self,
        *,
        app_job_id: str,
        compute_job_id: str,
        report_path: Path,
        metadata: dict[str, Any],
    ) -> tuple[str, str]:
        self.ensure_bucket()

        prefix = f"simulations/{app_job_id}"
        report_key = f"{prefix}/reporte.pdf"
        metadata_key = f"{prefix}/metadata.json"

        self._client.fput_object(
            bucket_name=self.bucket,
            object_name=report_key,
            file_path=str(report_path),
            content_type="application/pdf",
            metadata={"app-job-id": app_job_id, "compute-job-id": compute_job_id},
        )

        payload = json.dumps(metadata, ensure_ascii=True, separators=(",", ":")).encode(
            "utf-8"
        )
        self._client.put_object(
            bucket_name=self.bucket,
            object_name=metadata_key,
            data=BytesIO(payload),
            length=len(payload),
            content_type="application/json",
        )

        return self.bucket, report_key

    def presigned_get_url(self, object_name: str, *, minutes: int = 10) -> str:
        return self._client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_name,
            expires=timedelta(minutes=minutes),
        )


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


artifact_store = ArtifactStore()
