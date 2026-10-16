import json
import subprocess
import sys

_PROBE = (
    "import json; from api.core import settings; "
    "print(json.dumps({"
    "'bucket': settings.S3_BUCKET, 'pool': settings.DB_POOL_MAX_SIZE, "
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
            "TSDHN_S3_BUCKET": "b",
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


def _setting(name: str, env: dict[str, str]) -> object:
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            f"import json; from api.core import settings; "
            f"print(json.dumps(settings.{name}))",
        ],
        env={"PATH": "", **env},
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(result.stdout)


def test_retention_runs_unless_turned_off() -> None:
    assert _setting("RETENTION_ENABLED", {}) is True
    assert _setting("RETENTION_ENABLED", {"TSDHN_RETENTION_ENABLED": "true"}) is True
    assert _setting("RETENTION_ENABLED", {"TSDHN_RETENTION_ENABLED": "false"}) is False
    assert _setting("RETENTION_ENABLED", {"TSDHN_RETENTION_ENABLED": "0"}) is False
