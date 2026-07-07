"""
The synchronous `/calculations` route exercises the real `TsunamiCalculator`
against the bundled model data; worker execution and MinIO uploads are covered
by the docker-compose end-to-end check, not here.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.core.jobs as jobs_module
import api.routes as routes
from api.core.jobs import (
    ComputeJobs,
    ReportDownload,
    ReportInvariantError,
    ReportMissingError,
    ReportNotReadyError,
    ReportStorageError,
    ReportTooLargeError,
)
from api.core.storage import StoredObjectInfo
from api.main import app

TOKEN = "test-service-token"
SAMPLE = {
    "Mw": 8.0,
    "h": 10.0,
    "lat0": -20.5,
    "lon0": -70.5,
    "hhmm": "0000",
    "dia": "23",
}
EXTERNAL_ID = "4cfe522f-7e7d-46e0-96ca-7b98743fb9f5"


@pytest.fixture(autouse=True)
def _service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("TSDHN_MODEL_DIR", str(Path("model").resolve()))


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def test_health_is_unauthenticated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ComputeJobsStub:
        def is_database_connected(self) -> bool:
            return True

        def is_storage_connected(self) -> bool:
            return True

    monkeypatch.setattr(routes, "compute_jobs", ComputeJobsStub())

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert set(response.json()) == {
        "status",
        "timestamp",
        "database_connected",
        "storage_connected",
    }


def test_version(client: TestClient) -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["name"] == "tsdhn-api"


def test_calculations_rejects_missing_token(client: TestClient) -> None:
    response = client.post("/api/v1/calculations", json=SAMPLE)
    assert response.status_code == 401


def test_calculations_returns_preview(client: TestClient) -> None:
    response = client.post("/api/v1/calculations", headers=_auth(), json=SAMPLE)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"calculation", "travel_times"}
    assert body["calculation"]["length"] > 0
    assert body["calculation"]["width"] > 0
    assert body["travel_times"]["arrival_times"]


def test_jobs_rejects_missing_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs",
        json={"app_job_id": EXTERNAL_ID, "input": SAMPLE, "skip_steps": []},
    )
    assert response.status_code == 401


def test_jobs_use_app_job_id_as_idempotency_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    class ComputeJobsStub:
        def create_or_get_job(self, **kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {
                "compute_job_id": "compute-job-123",
                "status": "queued",
                "result_bucket": None,
                "result_key": None,
            }

    monkeypatch.setattr(routes, "compute_jobs", ComputeJobsStub())

    response = client.post(
        "/api/v1/jobs",
        headers=_auth(),
        json={"app_job_id": EXTERNAL_ID, "input": SAMPLE, "skip_steps": []},
    )

    assert response.status_code == 201
    assert response.json() == {
        "app_job_id": EXTERNAL_ID,
        "compute_job_id": "compute-job-123",
        "status": "queued",
        "result_bucket": None,
        "result_key": None,
    }
    assert calls[0]["external_id"] == EXTERNAL_ID


def test_legacy_simulations_endpoint_is_removed(client: TestClient) -> None:
    response = client.post(
        "/api/v1/simulations",
        headers=_auth(),
        json={"app_job_id": EXTERNAL_ID, "input": SAMPLE, "skip_steps": []},
    )
    assert response.status_code == 404


def test_job_report_is_proxied_through_api(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ComputeJobsStub:
        def get_report_download(self, app_job_id: str) -> ReportDownload:
            assert app_job_id == EXTERNAL_ID
            return ReportDownload(
                content_type="application/pdf",
                size=16,
                chunks=iter([b"%PDF-1.7\n", b"report\n"]),
            )

    monkeypatch.setattr(routes, "compute_jobs", ComputeJobsStub())

    response = client.get(f"/api/v1/jobs/{EXTERNAL_ID}/report", headers=_auth())

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert (
        response.headers["content-disposition"] == 'attachment; filename="reporte.pdf"'
    )
    assert response.headers["content-length"] == "16"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content.startswith(b"%PDF")


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ReportNotReadyError("Report is not available"), 425),
        (ReportMissingError("Report object was not found"), 404),
        (ReportTooLargeError("Report object exceeds the download size limit"), 413),
        (ReportStorageError("Report storage is unavailable"), 503),
        (ReportInvariantError("Report metadata is inconsistent"), 500),
    ],
)
def test_job_report_errors_are_mapped(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
) -> None:
    class ComputeJobsStub:
        def get_report_download(self, app_job_id: str) -> ReportDownload:
            raise error

    monkeypatch.setattr(routes, "compute_jobs", ComputeJobsStub())

    response = client.get(f"/api/v1/jobs/{EXTERNAL_ID}/report", headers=_auth())

    assert response.status_code == status_code


def test_compute_report_download_enforces_expected_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_key = f"simulations/{EXTERNAL_ID}/reporte.pdf"
    streamed_keys: list[str] = []

    class ArtifactStoreStub:
        def stat_object(self, object_name: str) -> StoredObjectInfo:
            assert object_name == expected_key
            return StoredObjectInfo(
                object_name=object_name,
                size=16,
                content_type="application/pdf",
            )

        def stream_object(self, object_name: str) -> Iterator[bytes]:
            streamed_keys.append(object_name)
            return iter([b"%PDF-1.7\n", b"report\n"])

    compute_jobs = ComputeJobs()
    monkeypatch.setattr(
        compute_jobs,
        "get_job_status",
        lambda app_job_id: {
            "status": "completed",
            "result_bucket": "tsdhn-results",
            "result_key": expected_key,
        },
    )
    monkeypatch.setattr(jobs_module, "artifact_store", ArtifactStoreStub())

    report = compute_jobs.get_report_download(EXTERNAL_ID)

    assert report.content_type == "application/pdf"
    assert report.size == 16
    assert b"".join(report.chunks).startswith(b"%PDF")
    assert streamed_keys == [expected_key]


@pytest.mark.parametrize(
    ("status_override", "expected_error"),
    [
        ({"status": "running", "result_key": None}, ReportNotReadyError),
        (
            {"result_bucket": "other-bucket"},
            ReportInvariantError,
        ),
        (
            {"result_key": f"simulations/{EXTERNAL_ID}/unexpected.pdf"},
            ReportInvariantError,
        ),
    ],
)
def test_compute_report_download_rejects_invalid_job_metadata(
    monkeypatch: pytest.MonkeyPatch,
    status_override: dict[str, object],
    expected_error: type[Exception],
) -> None:
    expected_key = f"simulations/{EXTERNAL_ID}/reporte.pdf"
    status_payload = {
        "status": "completed",
        "result_bucket": "tsdhn-results",
        "result_key": expected_key,
        **status_override,
    }
    compute_jobs = ComputeJobs()
    monkeypatch.setattr(
        compute_jobs,
        "get_job_status",
        lambda app_job_id: status_payload,
    )

    with pytest.raises(expected_error):
        compute_jobs.get_report_download(EXTERNAL_ID)


@pytest.mark.parametrize(
    ("object_info", "expected_error"),
    [
        (
            StoredObjectInfo(
                object_name=f"simulations/{EXTERNAL_ID}/reporte.pdf",
                size=51,
                content_type="application/pdf",
            ),
            ReportTooLargeError,
        ),
        (
            StoredObjectInfo(
                object_name=f"simulations/{EXTERNAL_ID}/reporte.pdf",
                size=16,
                content_type="text/html",
            ),
            ReportInvariantError,
        ),
    ],
)
def test_compute_report_download_rejects_invalid_object_metadata(
    monkeypatch: pytest.MonkeyPatch,
    object_info: StoredObjectInfo,
    expected_error: type[Exception],
) -> None:
    expected_key = f"simulations/{EXTERNAL_ID}/reporte.pdf"

    class ArtifactStoreStub:
        def stat_object(self, object_name: str) -> StoredObjectInfo:
            return object_info

        def stream_object(self, object_name: str) -> Iterator[bytes]:
            raise AssertionError("Invalid report objects must not be streamed")

    compute_jobs = ComputeJobs()
    monkeypatch.setattr(
        compute_jobs,
        "get_job_status",
        lambda app_job_id: {
            "status": "completed",
            "result_bucket": "tsdhn-results",
            "result_key": expected_key,
        },
    )
    monkeypatch.setattr(jobs_module, "artifact_store", ArtifactStoreStub())
    monkeypatch.setattr(jobs_module, "REPORT_DOWNLOAD_MAX_BYTES", 50)

    with pytest.raises(expected_error):
        compute_jobs.get_report_download(EXTERNAL_ID)
