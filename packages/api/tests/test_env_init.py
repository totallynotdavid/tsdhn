import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "env-init.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("openssl") is None or shutil.which("bash") is None,
    reason="env-init.sh needs bash and openssl",
)

MAIN_ENV = {
    "API_IMAGE": "ghcr.io/example/tsdhn-api:v1",
    "TSDHN_PRIVATE_ADDR": "100.64.0.1",
    "COMPUTE_WORKER_PASSWORD": "worker-secret",
    "COMPUTE_PURGER_PASSWORD": "purger-secret",
    "COMPUTE_PRODUCER_PASSWORD": "producer-secret",
    "POSTGRES_PASSWORD": "owner-secret",
    "TSDHN_S3_ACCESS_KEY": "access",
    "TSDHN_S3_SECRET_KEY": "secret",
    "TSDHN_S3_BUCKET": "outputs",
}


def _run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT), *map(str, args)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _main_env(tmp_path: Path, **overrides: str | None) -> Path:
    values = {**MAIN_ENV, **overrides}
    path = tmp_path / "prod.env"
    path.write_text(
        "".join(f"{k}={v}\n" for k, v in values.items() if v is not None),
        encoding="utf-8",
    )
    return path


def _read(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )


def test_worker_env_points_at_the_private_address_and_an_external_store(
    tmp_path: Path,
) -> None:
    main = _main_env(
        tmp_path,
        TSDHN_S3_ENDPOINT="acct.r2.cloudflarestorage.com",
        TSDHN_S3_SECURE="true",
        TSDHN_S3_REGION="auto",
    )
    target = tmp_path / "worker.env"

    result = _run("--worker", "--from", main, target)

    assert result.returncode == 0, result.stderr
    env = _read(target)
    assert env["COMPUTE_RUNTIME_DATABASE_URL"] == "postgresql://100.64.0.1:5432/tsdhn"
    assert env["API_IMAGE"] == MAIN_ENV["API_IMAGE"]
    assert env["TSDHN_S3_ENDPOINT"] == "acct.r2.cloudflarestorage.com"
    assert env["TSDHN_S3_SECURE"] == "true"
    assert env["TSDHN_S3_REGION"] == "auto"
    assert env["COMPUTE_WORKER_PASSWORD"] == "worker-secret"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_worker_env_carries_no_credential_a_worker_does_not_need(
    tmp_path: Path,
) -> None:
    main = _main_env(tmp_path, TSDHN_S3_ENDPOINT="acct.r2.cloudflarestorage.com")
    target = tmp_path / "worker.env"

    assert _run("--worker", "--from", main, target).returncode == 0

    text = target.read_text(encoding="utf-8")
    for secret in ("purger-secret", "producer-secret", "owner-secret"):
        assert secret not in text


def test_worker_env_reaches_the_bundled_storage_on_the_private_address(
    tmp_path: Path,
) -> None:
    main = _main_env(tmp_path)
    target = tmp_path / "worker.env"

    result = _run("--worker", "--from", main, target)

    assert result.returncode == 0, result.stderr
    env = _read(target)
    assert env["TSDHN_S3_ENDPOINT"] == "100.64.0.1:9000"
    assert env["TSDHN_S3_SECURE"] == "false"
    assert env["TSDHN_S3_REGION"] == "us-east-1"


def test_worker_env_states_the_connection_settings_the_main_env_leaves_to_defaults(
    tmp_path: Path,
) -> None:
    main = _main_env(tmp_path, TSDHN_S3_ENDPOINT="s3.example.org")
    target = tmp_path / "worker.env"

    assert _run("--worker", "--from", main, target).returncode == 0

    env = _read(target)
    assert env["TSDHN_S3_SECURE"] == "false"
    assert env["TSDHN_S3_REGION"] == "us-east-1"


@pytest.mark.parametrize(
    "missing", ["TSDHN_PRIVATE_ADDR", "API_IMAGE", "COMPUTE_WORKER_PASSWORD"]
)
def test_worker_env_stops_and_names_a_missing_value(
    tmp_path: Path, missing: str
) -> None:
    main = _main_env(
        tmp_path, TSDHN_S3_ENDPOINT="acct.r2.cloudflarestorage.com", **{missing: None}
    )
    target = tmp_path / "worker.env"

    result = _run("--worker", "--from", main, target)

    assert result.returncode != 0
    assert missing in result.stderr
    assert not target.exists()


def test_env_init_refuses_to_overwrite_an_existing_file(tmp_path: Path) -> None:
    main = _main_env(tmp_path, TSDHN_S3_ENDPOINT="acct.r2.cloudflarestorage.com")
    target = tmp_path / "worker.env"
    target.write_text("keep\n", encoding="utf-8")

    result = _run("--worker", "--from", main, target)

    assert result.returncode != 0
    assert target.read_text(encoding="utf-8") == "keep\n"


def test_main_env_gets_a_generated_secret_for_every_password(tmp_path: Path) -> None:
    target = tmp_path / "prod.env"

    result = _run(target)

    assert result.returncode == 0, result.stderr
    env = _read(target)
    for name in (
        "POSTGRES_PASSWORD",
        "COMPUTE_WORKER_PASSWORD",
        "COMPUTE_PURGER_PASSWORD",
        "TSDHN_S3_SECRET_KEY",
    ):
        assert len(env[name]) >= 20
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
