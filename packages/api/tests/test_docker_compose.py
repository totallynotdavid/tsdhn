"""Checks for privilege-bearing environment variables in service wiring."""

import re
from pathlib import Path


def _service_block(compose: str, service: str) -> str:
    start = compose.index(f"  {service}:\n")
    following = re.search(r"^  [a-zA-Z0-9_-]+:\n", compose[start + 1 :], re.MULTILINE)
    end = start + 1 + following.start() if following else len(compose)
    return compose[start:end]


def test_long_running_services_do_not_receive_the_owner_dsn() -> None:
    compose = (Path(__file__).parents[3] / "docker-compose.yml").read_text()

    assert "COMPUTE_DATABASE_URL:" in _service_block(compose, "compute-migrate")
    assert "COMPUTE_DATABASE_URL:" in _service_block(compose, "web-grants")
    for service in ("api", "worker"):
        block = _service_block(compose, service)
        assert "COMPUTE_DATABASE_URL:" not in block
        assert "COMPUTE_RUNTIME_DATABASE_URL:" in block


def test_api_image_does_not_bake_the_owner_dsn() -> None:
    dockerfile = (Path(__file__).parents[3] / "deploy/api.Dockerfile").read_text()

    assert "COMPUTE_DATABASE_URL=" not in dockerfile
