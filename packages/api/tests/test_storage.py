from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

import pytest
from minio.error import MinioException as S3ClientError
from minio.error import S3Error

from api.core.errors import TransientInfraError
from api.core.storage import OutputStore
from tsdhn.engine import OutputFile, SimulationOutputs


class _RaisingStorageClient:
    def bucket_exists(self, bucket_name: str) -> bool:
        return True

    def fput_object(self, **kwargs: object) -> None:
        raise S3ClientError("simulated storage outage")


class _RaisingPresignClient:
    def presigned_get_object(self, **kwargs: object) -> str:
        raise S3ClientError("simulated storage outage")


class _RecordingStorageClient:
    def __init__(self) -> None:
        self.created_bucket = False
        self.uploads: list[dict[str, Any]] = []
        self.metadata_uploads: list[dict[str, Any]] = []
        self.presign: dict[str, Any] | None = None

    def bucket_exists(self, bucket_name: str) -> bool:
        return self.created_bucket

    def make_bucket(self, bucket_name: str) -> None:
        self.created_bucket = True

    def fput_object(self, **kwargs: Any) -> None:
        self.uploads.append(kwargs)

    def put_object(self, **kwargs: Any) -> None:
        payload = kwargs["data"].read()
        self.metadata_uploads.append({**kwargs, "payload": payload})

    def presigned_get_object(self, **kwargs: Any) -> str:
        self.presign = kwargs
        return "https://storage.example/signed"


def test_upload_simulation_result_wraps_storage_failure(tmp_path: Path) -> None:
    store = OutputStore.__new__(OutputStore)
    store.bucket = "tsdhn-results"
    store._client = _RaisingStorageClient()  # type: ignore[assignment]

    output_path = tmp_path / "maxola.pdf"
    output_path.write_bytes(b"%PDF-1.4\n")
    outputs = SimulationOutputs(
        root=tmp_path,
        files=(OutputFile("max_height_map", output_path, "application/pdf"),),
    )

    with pytest.raises(TransientInfraError):
        store.upload_simulation_result(
            simulation_id="job-1",
            compute_job_id="compute-1",
            outputs=outputs,
            metadata={},
        )


def test_presigned_url_wraps_storage_failure() -> None:
    store = OutputStore.__new__(OutputStore)
    store.bucket = "tsdhn-results"
    store._client = _RaisingPresignClient()  # type: ignore[assignment]

    with pytest.raises(TransientInfraError, match="presigning output URL failed"):
        store.presigned_url("simulations/job-1/result.pdf", filename="result.pdf")


def test_upload_simulation_result_creates_bucket_and_persists_manifest(
    tmp_path: Path,
) -> None:
    store = OutputStore.__new__(OutputStore)
    store.bucket = "tsdhn-results"
    client = _RecordingStorageClient()
    store._client = client  # type: ignore[assignment]

    output_path = tmp_path / "maxola.pdf"
    output_path.write_bytes(b"pdf")
    outputs = SimulationOutputs(
        root=tmp_path,
        files=(OutputFile("max_height_map", output_path, "application/pdf"),),
    )

    bucket, metadata_key = store.upload_simulation_result(
        simulation_id="job-1",
        compute_job_id="compute-1",
        outputs=outputs,
        metadata={"status": "completed"},
    )

    assert (bucket, metadata_key) == (
        "tsdhn-results",
        "simulations/job-1/metadata.json",
    )
    assert client.created_bucket
    assert client.uploads[0]["object_name"] == ("simulations/job-1/outputs/maxola.pdf")
    assert client.uploads[0]["metadata"] == {
        "simulation-id": "job-1",
        "compute-job-id": "compute-1",
        "output-name": "max_height_map",
    }
    assert client.metadata_uploads[0]["payload"] == b'{"status":"completed"}'
    assert client.metadata_uploads[0]["content_type"] == "application/json"


def test_presigned_url_names_the_download_filename() -> None:
    store = OutputStore.__new__(OutputStore)
    store.bucket = "tsdhn-results"
    client = _RecordingStorageClient()
    store._client = client  # type: ignore[assignment]

    url = store.presigned_url("simulations/job-1/result.pdf", filename="result.pdf")

    assert url == "https://storage.example/signed"
    assert client.presign is not None
    assert client.presign["bucket_name"] == "tsdhn-results"
    assert client.presign["object_name"] == "simulations/job-1/result.pdf"
    assert client.presign["response_headers"] == {
        "response-content-disposition": 'attachment; filename="result.pdf"'
    }


def test_client_uses_fixed_s3_region(monkeypatch: pytest.MonkeyPatch) -> None:
    clients: list[dict[str, Any]] = []

    class _RecordingClient:
        def __init__(self, *_args: object, **kwargs: object) -> None:
            clients.append(kwargs)

    monkeypatch.setattr("api.core.storage.S3Client", _RecordingClient)

    OutputStore()

    assert [client["region"] for client in clients] == ["us-east-1"]


def test_the_download_url_for_an_r2_endpoint_is_https_and_signed_for_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Presigning is local arithmetic: no request reaches the endpoint."""
    host = "0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com"
    for name, value in (
        ("S3_ENDPOINT", host),
        ("S3_SECURE", True),
        ("S3_REGION", "auto"),
        ("S3_BUCKET", "tsdhn-results"),
    ):
        monkeypatch.setattr(f"api.core.storage.{name}", value)

    url = OutputStore().presigned_url(
        "simulations/job-1/outputs/map.pdf", filename="map.pdf"
    )

    parts = urlsplit(url)
    query = parse_qs(parts.query)
    assert (parts.scheme, parts.netloc) == ("https", host)
    assert parts.path == "/tsdhn-results/simulations/job-1/outputs/map.pdf"
    assert query["X-Amz-Credential"][0].endswith("/auto/s3/aws4_request")
    assert query["response-content-disposition"] == ['attachment; filename="map.pdf"']


class _BucketLookupClient:
    def __init__(self, code: str) -> None:
        self.code = code
        self.made = False

    def bucket_exists(self, bucket_name: str) -> bool:
        raise S3Error(cast(Any, None), self.code, "refused", None, None, None)

    def make_bucket(self, bucket_name: str) -> None:
        self.made = True


def _store_with(client: _BucketLookupClient) -> OutputStore:
    store = OutputStore.__new__(OutputStore)
    store.bucket = "tsdhn-results"
    store._client = client  # type: ignore[assignment]
    return store


def test_a_key_refused_the_bucket_lookup_still_reaches_its_bucket() -> None:
    client = _BucketLookupClient("AccessDenied")
    store = _store_with(client)

    assert store.is_connected()
    store.ensure_bucket()
    assert not client.made


def test_a_failed_bucket_lookup_other_than_a_refusal_is_an_outage() -> None:
    store = _store_with(_BucketLookupClient("InternalError"))

    assert not store.is_connected()
    with pytest.raises(S3Error):
        store.ensure_bucket()
