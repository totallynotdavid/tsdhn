"""Dockerfile ARG defaults must mirror the versions pinned in .tool-versions."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]


def _pinned(tool: str) -> str:
    for line in (ROOT / ".tool-versions").read_text().splitlines():
        name, _, version = line.partition(" ")
        if name == tool:
            return version.strip()
    raise AssertionError(f"{tool} is not pinned in .tool-versions")


@pytest.mark.parametrize(
    ("dockerfile", "arg", "tool"),
    [
        ("deploy/api.Dockerfile", "UV_VERSION", "uv"),
        ("deploy/web.Dockerfile", "BUN_VERSION", "bun"),
    ],
)
def test_dockerfile_arg_default_matches_tool_versions(
    dockerfile: str, arg: str, tool: str
) -> None:
    text = (ROOT / dockerfile).read_text()

    match = re.search(rf"^ARG {arg}=(\S+)$", text, re.MULTILINE)

    assert match, f"{dockerfile} must declare ARG {arg} with a default"
    assert match.group(1) == _pinned(tool)
