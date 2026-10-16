"""Throwaway containers for tests that need a real PostgreSQL or object store.

Docker is the only requirement: a test module calls `require_docker()` at import
and skips when the daemon or an image is missing.
"""

from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest
from minio import Minio

REPO_ROOT = Path(__file__).resolve().parents[3]
POSTGRES_IMAGE = "postgres:18-alpine"
STORAGE_IMAGE = "docker.io/rustfs/rustfs:1.0.1"

DB_PASSWORD = "backup-test-db-password"
S3_KEY = "backup-test-key"
S3_SECRET = "backup-test-secret-0123456789"
BUCKET = "tsdhn-results"
BACKUP_PASSWORD = "backup-test-repository-password"
OFFSITE_BUCKET = "offsite-backups"
ROLE_PASSWORD = "backup-test-role-password"
API_TOKEN = "backup-test-api-token"


def docker(
    *args: str, check: bool = True, stdin: bytes | None = None, timeout: float = 600
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(  # noqa: S603
        ["docker", *args],  # noqa: S607
        input=stdin,
        capture_output=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"docker {' '.join(args[:2])} failed ({result.returncode}):\n"
            f"{result.stdout.decode(errors='replace')[-2000:]}\n"
            f"{result.stderr.decode(errors='replace')[-2000:]}"
        )
    return result


def require_docker() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker is not installed", allow_module_level=True)
    if docker("info", check=False).returncode != 0:
        pytest.skip("the docker daemon is not reachable", allow_module_level=True)
    for image in (POSTGRES_IMAGE, STORAGE_IMAGE):
        if docker("image", "inspect", image, check=False).returncode == 0:
            continue
        if docker("pull", image, check=False).returncode != 0:
            pytest.skip(f"{image} is not available", allow_module_level=True)


@dataclass(frozen=True)
class Service:
    name: str
    host_port: int

    @property
    def local(self) -> str:
        return f"127.0.0.1:{self.host_port}"


class Lab:
    """The containers of one test module, removed together."""

    def __init__(self) -> None:
        self.tag = uuid.uuid4().hex[:10]
        self.network = f"tsdhn-bk-{self.tag}"
        self.image = f"tsdhn-backup:test-{self.tag}"
        self._containers: list[str] = []

    def setup_network(self) -> None:
        docker("network", "create", self.network)

    def setup(self, context: Path) -> None:
        """Build the image from a context holding only the files it copies."""
        self.setup_network()
        shutil.copy(REPO_ROOT / "deploy/backup.Dockerfile", context / "Dockerfile")
        shutil.copytree(REPO_ROOT / "deploy/backup", context / "deploy/backup")
        docker("build", "-t", self.image, str(context))

    def teardown(self) -> None:
        if self._containers:
            docker("rm", "-f", "-v", *self._containers, check=False)
        docker("network", "rm", self.network, check=False)
        docker("rmi", self.image, check=False)

    def _run(
        self, name: str, image: str, *args: str, publish: int, command: str = ""
    ) -> Service:
        container = f"{self.network}-{name}"
        docker(
            "run",
            "-d",
            "--name",
            container,
            "--network",
            self.network,
            "--network-alias",
            name,
            "-p",
            f"127.0.0.1::{publish}",
            *args,
            image,
            *([command] if command else []),
        )
        self._containers.append(container)
        mapped = docker("port", container, str(publish)).stdout.decode()
        return Service(name, int(mapped.splitlines()[0].rsplit(":", 1)[1]))

    def postgres(self, name: str) -> Service:
        service = self._run(
            name,
            POSTGRES_IMAGE,
            "-e",
            f"POSTGRES_PASSWORD={DB_PASSWORD}",
            "-e",
            "POSTGRES_USER=tsdhn",
            "-e",
            "POSTGRES_DB=tsdhn",
            publish=5432,
        )
        deadline = time.monotonic() + 60
        while True:
            try:
                psycopg.connect(self.database_url(service), connect_timeout=2).close()
                return service
            except psycopg.OperationalError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)

    def storage(self, name: str) -> Service:
        service = self._run(
            name,
            STORAGE_IMAGE,
            "-e",
            f"RUSTFS_ACCESS_KEY={S3_KEY}",
            "-e",
            f"RUSTFS_SECRET_KEY={S3_SECRET}",
            "-e",
            "RUSTFS_VOLUMES=/data",
            "-e",
            "RUSTFS_ADDRESS=:9000",
            "-e",
            "RUSTFS_CONSOLE_ENABLE=false",
            publish=9000,
            command="/data",
        )
        deadline = time.monotonic() + 90
        while True:
            try:
                self.client(service).list_buckets()
                return service
            except Exception:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"{name} never answered") from None
                time.sleep(0.5)

    @staticmethod
    def database_url(service: Service) -> str:
        return f"postgresql://tsdhn:{DB_PASSWORD}@{service.local}/tsdhn"

    @staticmethod
    def client(service: Service) -> Minio:
        return Minio(
            service.local,
            access_key=S3_KEY,
            secret_key=S3_SECRET,
            secure=False,
            region="us-east-1",
        )

    def run_backup_image(
        self,
        command: list[str],
        *,
        database: Service,
        objects: Service,
        offsite: Service,
        password: str = BACKUP_PASSWORD,
        entrypoint: str | None = None,
        overrides: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        env = {
            "RESTIC_REPOSITORY": f"s3:http://{offsite.name}:9000/{OFFSITE_BUCKET}",
            "RESTIC_PASSWORD": password,
            "AWS_ACCESS_KEY_ID": S3_KEY,
            "AWS_SECRET_ACCESS_KEY": S3_SECRET,
            "PGHOST": database.name,
            "PGUSER": "tsdhn",
            "PGDATABASE": "tsdhn",
            "PGPASSWORD": DB_PASSWORD,
            "TSDHN_S3_ENDPOINT": f"{objects.name}:9000",
            "TSDHN_S3_ACCESS_KEY": S3_KEY,
            "TSDHN_S3_SECRET_KEY": S3_SECRET,
            "TSDHN_S3_BUCKET": BUCKET,
        }
        env |= overrides or {}
        flags = [
            part for key, value in env.items() for part in ("-e", f"{key}={value}")
        ]
        if entrypoint is not None:
            flags += ["--entrypoint", entrypoint]
        return docker(
            "run", "--rm", "--network", self.network, *flags, self.image, *command,
            check=False,
        )  # fmt: skip
