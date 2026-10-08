import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]

_PROBE = (
    "import json; from api.core import settings; "
    "print(json.dumps({"
    "'bucket': settings.MINIO_BUCKET, 'pool': settings.DB_POOL_MAX_SIZE, "
    "'ttl': settings.OUTPUT_URL_TTL, 'sse': settings.SSE_MAX_DURATION, "
    "'origins': settings.ALLOWED_ORIGINS, 'port': settings.API_PORT}))"
)


def _settings(env: dict[str, str]) -> dict[str, object]:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _PROBE],
        env={"PATH": "", **env},
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def test_service_settings_read_tsdhn_prefixed_names() -> None:
    values = _settings(
        {
            "TSDHN_MINIO_BUCKET": "b",
            "TSDHN_DB_POOL_MAX_SIZE": "3",
            "TSDHN_OUTPUT_URL_TTL_SECONDS": "7",
            "TSDHN_SSE_MAX_DURATION_SECONDS": "11",
            "TSDHN_ALLOWED_ORIGINS": "http://a,http://b",
            "TSDHN_PORT": "9001",
        }
    )

    assert values == {
        "bucket": "b",
        "pool": 3,
        "ttl": 7,
        "sse": 11,
        "origins": ["http://a", "http://b"],
        "port": 9001,
    }


def test_unprefixed_names_are_ignored() -> None:
    values = _settings(
        {
            "MINIO_BUCKET": "legacy",
            "DB_POOL_MAX_SIZE": "99",
            "OUTPUT_URL_TTL_SECONDS": "99",
            "SSE_MAX_DURATION_SECONDS": "99",
            "ALLOWED_ORIGINS": "http://legacy",
            "APP_PORT": "1",
        }
    )

    assert values == {
        "bucket": "tsdhn-results",
        "pool": 10,
        "ttl": 900,
        "sse": 1800,
        "origins": [],
        "port": 8000,
    }


def test_compose_owns_the_runtime_database_endpoint() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text()
    example = (REPO_ROOT / ".env.example").read_text()

    assert "COMPUTE_RUNTIME_DATABASE_URL: postgresql://postgres:5432/tsdhn" in compose
    assert "COMPUTE_RUNTIME_DATABASE_URL" not in example
