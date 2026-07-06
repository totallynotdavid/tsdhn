"""
The synchronous `/calculations` route exercises the real `TsunamiCalculator`
against the bundled model data; worker execution and MinIO uploads are covered
by the docker-compose end-to-end check, not here.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.routes as routes
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
