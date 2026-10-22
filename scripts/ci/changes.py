"""Decide which CI jobs a change needs.

The script reads the GitHub event from the environment (EVENT_NAME, REF,
BEFORE_SHA, and HEAD_FORK for a pull request from a fork) and prints switches in
the ``$GITHUB_OUTPUT`` format. Unknown changes turn every job on. It uses only
the standard library so the runner's ``python3`` can execute it.
"""

import os
import subprocess
import sys
from fnmatch import fnmatch

DOCS = ("*.md", "docs/*")

# What the image jobs and the compose smoke build or run that a change to the
# packages cannot reach. Each group is read from the file that consumes it.
# `*` in a pattern also matches `/`.
IMAGE_INPUTS = (
    ".github/workflows/release.yml",
    ".github/release-notes.md",
    "deploy/*",
    ".devcontainer/Dockerfile",
    "docker-compose*.yml",
    ".dockerignore",
    # The Dockerfiles copy these files or read their build arguments.
    "mise.toml",
    "pyproject.toml",
    "uv.lock",
    # `COPY packages` and `uv sync --frozen`: the dependencies and entry points.
    "packages/*/pyproject.toml",
    "model/*",
    # The web image reads these manifests and its adapter configuration.
    "package.json",
    "bun.lock",
    "apps/web/package.json",
    "apps/web/vite.config.ts",
    "libs/api-client/package.json",
    "scripts/e2e/*",
)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def changed_files(event: str, before: str) -> list[str] | None:
    """Return the files the event changed, or None when the diff is unknown."""
    if event == "pull_request":
        # The merge commit's first parent is the pull request base.
        base = "HEAD^1"
    elif event == "push" and before.strip("0"):
        base = before
    else:
        return None
    missing = git("cat-file", "-e", f"{base}^{{commit}}").returncode
    if missing and git("fetch", "--no-tags", "--depth=1", "origin", base).returncode:
        return None
    diff = git("diff", "--name-only", base, "HEAD")
    return None if diff.returncode else diff.stdout.splitlines()


def matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def touches_images(files: list[str] | None) -> bool:
    return files is None or any(matches(path, IMAGE_INPUTS) for path in files)


def ci(event: str, files: list[str] | None) -> dict[str, bool]:
    docs_only = (
        event == "pull_request"
        and bool(files)
        and all(matches(path, DOCS) for path in files)
    )
    return {"code": not docs_only, "docs": docs_only}


def release(
    event: str, ref: str, files: list[str] | None, fork: bool
) -> dict[str, bool]:
    if event == "push" and ref == "refs/heads/master":
        # Master only warms image caches because the pull request ran the dry run.
        return {"release": False, "images": False, "warm": touches_images(files)}
    # A fork's token cannot push candidate images, so a fork builds none.
    images = not fork and (event != "pull_request" or touches_images(files))
    return {"release": True, "images": images, "warm": False}


def main() -> None:
    workflow = sys.argv[1] if len(sys.argv) == 2 else ""
    if workflow not in ("ci", "release"):
        sys.exit(__doc__)
    event = os.environ["EVENT_NAME"]
    files = changed_files(event, os.environ.get("BEFORE_SHA", ""))
    print(
        f"{event}: {'unknown change' if files is None else f'{len(files)} files'}",
        file=sys.stderr,
    )
    switches = (
        ci(event, files)
        if workflow == "ci"
        else release(
            event, os.environ["REF"], files, os.environ.get("HEAD_FORK") == "true"
        )
    )
    for name, value in switches.items():
        print(f"{name}={str(value).lower()}")


if __name__ == "__main__":
    main()
