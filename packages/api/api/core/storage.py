import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
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
from tsdhn.engine import ArtifactBundle

__all__ = ["ArtifactStore", "StoredObjectInfo", "artifact_store"]


@dataclass(frozen=True)
class StoredObjectInfo:
    object_name: str
    size: int
    content_type: str | None


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
        bundle: ArtifactBundle,
        metadata: dict[str, Any],
    ) -> tuple[str, str]:
        self.ensure_bucket()

        prefix = f"simulations/{app_job_id}"
        metadata_key = f"{prefix}/metadata.json"

        for artifact in bundle.artifacts:
            self._client.fput_object(
                bucket_name=self.bucket,
                object_name=f"{prefix}/artifacts/{artifact.path.name}",
                file_path=str(artifact.path),
                content_type=artifact.content_type,
                metadata={
                    "app-job-id": app_job_id,
                    "compute-job-id": compute_job_id,
                    "artifact-name": artifact.name,
                },
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

        return self.bucket, metadata_key

    def stat_object(self, object_name: str) -> StoredObjectInfo:
        result = self._client.stat_object(
            bucket_name=self.bucket,
            object_name=object_name,
        )
        return StoredObjectInfo(
            object_name=object_name,
            size=int(result.size or 0),
            content_type=result.content_type,
        )

    def stream_object(
        self, object_name: str, *, chunk_size: int = 1024 * 1024
    ) -> Iterator[bytes]:
        response = self._client.get_object(
            bucket_name=self.bucket,
            object_name=object_name,
        )
        try:
            yield from response.stream(chunk_size)
        finally:
            response.close()
            response.release_conn()


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


artifact_store = ArtifactStore()
