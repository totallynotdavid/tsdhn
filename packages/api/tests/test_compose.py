"""The production Compose files, rendered by `docker compose config`."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None, reason="needs the docker CLI"
)

MAIN_ENV = {
    "API_IMAGE": "ghcr.io/example/tsdhn-api:v1",
    "WEB_IMAGE": "ghcr.io/example/tsdhn-web:v1",
    "BACKUP_IMAGE": "ghcr.io/example/tsdhn-backup:v1",
    "BACKUP_REPOSITORY": "s3:https://backup.example.org/bucket",
    "BACKUP_PASSWORD": "x",
    "BACKUP_S3_ACCESS_KEY": "x",
    "BACKUP_S3_SECRET_KEY": "x",
    "POSTGRES_PASSWORD": "x",
    "APP_DB_PASSWORD": "x",
    "COMPUTE_API_TOKEN": "x",
    "COMPUTE_PRODUCER_PASSWORD": "x",
    "COMPUTE_WORKER_PASSWORD": "x",
    "COMPUTE_PURGER_PASSWORD": "x",
    "BETTER_AUTH_SECRET": "x",
    "ORIGIN": "https://example.org",
    "TUNNEL_TOKEN": "x",
    "TSDHN_S3_ACCESS_KEY": "access",
    "TSDHN_S3_SECRET_KEY": "secret",
}

WORKER_ENV = {
    "API_IMAGE": "ghcr.io/example/tsdhn-api:v1",
    "COMPUTE_RUNTIME_DATABASE_URL": "postgresql://100.64.0.1:5432/tsdhn",
    "COMPUTE_WORKER_PASSWORD": "x",
    "TSDHN_S3_ENDPOINT": "s3.example.org",
    "TSDHN_S3_ACCESS_KEY": "access",
    "TSDHN_S3_SECRET_KEY": "secret",
}


def _config(
    tmp_path: Path, env: dict[str, str], *files: str
) -> subprocess.CompletedProcess[str]:
    env_file = tmp_path / "test.env"
    env_file.write_text("".join(f"{k}={v}\n" for k, v in env.items()), encoding="utf-8")
    command = ["docker", "compose", "--env-file", str(env_file)]
    for name in files:
        command += ["-f", str(DEPLOY / name)]
    return subprocess.run(  # noqa: S603
        [*command, "config", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )


def _services(
    tmp_path: Path, env: dict[str, str], *files: str
) -> dict[str, dict[str, Any]]:
    result = _config(tmp_path, env, *files)
    assert result.returncode == 0, result.stderr
    services: dict[str, dict[str, Any]] = json.loads(result.stdout)["services"]
    return services


def test_an_external_store_removes_the_bundled_storage_and_every_wait_for_it(
    tmp_path: Path,
) -> None:
    env = {
        **MAIN_ENV,
        "TSDHN_S3_ENDPOINT": "acct.r2.cloudflarestorage.com",
        "TSDHN_PRIVATE_ADDR": "100.64.0.1",
    }

    services = _services(
        tmp_path,
        env,
        "compose.prod.yml",
        "compose.private.yml",
        "compose.external-storage.yml",
    )

    assert "storage" not in services
    for service in services.values():
        assert "storage" not in service.get("depends_on", {})


def test_postgres_publishes_a_port_only_with_the_private_file(tmp_path: Path) -> None:
    env = {**MAIN_ENV, "TSDHN_PRIVATE_ADDR": "100.64.0.1"}

    plain = _services(tmp_path, env, "compose.prod.yml")
    private = _services(tmp_path, env, "compose.prod.yml", "compose.private.yml")

    assert "ports" not in plain["postgres"]
    assert [(p["host_ip"], p["published"]) for p in private["postgres"]["ports"]] == [
        ("100.64.0.1", "5432")
    ]


def test_the_worker_host_and_the_main_host_connect_to_the_store_the_same_way(
    tmp_path: Path,
) -> None:
    env = {**WORKER_ENV}
    main = _services(
        tmp_path,
        {**MAIN_ENV, "TSDHN_S3_ENDPOINT": env["TSDHN_S3_ENDPOINT"]},
        "compose.prod.yml",
    )["worker"]["environment"]
    remote = _services(tmp_path, env, "compose.worker.yml")["worker"]["environment"]

    for name in (
        "TSDHN_S3_ENDPOINT",
        "TSDHN_S3_SECURE",
        "TSDHN_S3_REGION",
        "TSDHN_S3_BUCKET",
    ):
        assert remote[name] == main[name], name


@pytest.mark.parametrize("missing", sorted(set(WORKER_ENV)))
def test_the_worker_host_stops_and_names_a_missing_value(
    tmp_path: Path, missing: str
) -> None:
    env = {k: v for k, v in WORKER_ENV.items() if k != missing}

    result = _config(tmp_path, env, "compose.worker.yml")

    assert result.returncode != 0
    assert missing in result.stderr
