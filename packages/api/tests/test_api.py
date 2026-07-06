"""
The synchronous `/calculations` route exercises the real `TsunamiCalculator`
against the bundled model data; enqueue/status/report paths need a live worker
and are covered by the docker-compose end-to-end check, not here.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture(autouse=True)
def _service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_SERVICE_TOKEN", TOKEN)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def test_health_is_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


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
