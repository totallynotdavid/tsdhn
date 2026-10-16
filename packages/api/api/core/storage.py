import json
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

import urllib3
from minio import Minio as S3Client
from minio.error import MinioException as S3ClientError
from minio.error import S3Error

from api.core.errors import TransientInfraError
from api.core.settings import (
    OUTPUT_URL_TTL,
    S3_ACCESS_KEY,
    S3_BUCKET,
    S3_ENDPOINT,
    S3_REGION,
    S3_SECRET_KEY,
    S3_SECURE,
)
from tsdhn.engine import SimulationOutputs

__all__ = ["OutputStore", "output_store"]


class OutputStore:
    def __init__(self) -> None:
        self.bucket = S3_BUCKET
        self._client = S3Client(
            S3_ENDPOINT,
            access_key=S3_ACCESS_KEY,
            secret_key=S3_SECRET_KEY,
            secure=S3_SECURE,
            # A fixed region makes presigning local arithmetic. Without one the
            # client asks the endpoint for the bucket region first.
            region=S3_REGION,
            http_client=urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=2.0, read=2.0),
                retries=False,
            ),
        )

    def _bucket_exists(self) -> bool:
        """Treat a bucket-lookup refusal as proof that the bucket is usable."""
        try:
            return self._client.bucket_exists(self.bucket)
        except S3Error as e:
            if e.code == "AccessDenied":
                return True
            raise

    def is_connected(self) -> bool:
        try:
            self._bucket_exists()
            return True
        except Exception:
            return False

    def ensure_bucket(self) -> None:
        if not self._bucket_exists():
            self._client.make_bucket(self.bucket)

    def upload_simulation_result(
        self,
        *,
        simulation_id: str,
        compute_job_id: str,
        outputs: SimulationOutputs,
        metadata: dict[str, Any],
    ) -> tuple[str, str]:
        prefix = f"simulations/{simulation_id}"
        metadata_key = f"{prefix}/metadata.json"

        try:
            self.ensure_bucket()

            for output in outputs.files:
                self._client.fput_object(
                    bucket_name=self.bucket,
                    object_name=f"{prefix}/outputs/{output.path.name}",
                    file_path=str(output.path),
                    content_type=output.content_type,
                    metadata={
                        "simulation-id": simulation_id,
                        "compute-job-id": compute_job_id,
                        "output-name": output.name,
                    },
                )

            payload = json.dumps(
                metadata, ensure_ascii=True, separators=(",", ":")
            ).encode("utf-8")
            self._client.put_object(
                bucket_name=self.bucket,
                object_name=metadata_key,
                data=BytesIO(payload),
                length=len(payload),
                content_type="application/json",
            )
        except (S3ClientError, urllib3.exceptions.HTTPError, OSError) as e:
            # Storage outages are transient. Let the task retry the upload.
            raise TransientInfraError("output upload failed") from e

        return self.bucket, metadata_key

    def delete_simulation_outputs(self, simulation_id: str) -> int:
        """Delete every object stored for a simulation and return how many.

        Deleting nothing is not an error, so a pass that died between this call
        and its database write can repeat it.
        """
        prefix = f"simulations/{simulation_id}/"
        try:
            names = [
                obj.object_name
                for obj in self._client.list_objects(
                    self.bucket, prefix=prefix, recursive=True
                )
                if obj.object_name
            ]
            for name in names:
                self._client.remove_object(self.bucket, name)
        except (S3ClientError, urllib3.exceptions.HTTPError, OSError) as e:
            raise TransientInfraError("deleting expired outputs failed") from e
        return len(names)

    def presigned_url(self, object_name: str, *, filename: str) -> str:
        """Return a short-lived URL for downloading an output file."""
        try:
            return self._client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=object_name,
                expires=timedelta(seconds=OUTPUT_URL_TTL),
                response_headers={
                    "response-content-disposition": (
                        f'attachment; filename="{filename}"'
                    )
                },
            )
        except (S3ClientError, urllib3.exceptions.HTTPError, OSError) as e:
            raise TransientInfraError("presigning output URL failed") from e


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


output_store = OutputStore()
