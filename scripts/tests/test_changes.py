"""Run scripts/ci/changes.py on real git history, as the workflows do."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "ci" / "changes.py"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
ZEROS = "0" * 40


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        [*GIT, *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def commit_files(repo: Path, paths: list[str], message: str) -> None:
    for path in paths:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{message}\n{target.read_text() if target.exists() else ''}")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-b", "master")
    commit_files(tmp_path, ["readme.md", "uv.lock"], "base")
    return tmp_path


def merge_pull_request(repo: Path, paths: list[str]) -> None:
    """Leave the repo on the merge of a branch that changes paths into master."""
    git(repo, "switch", "-c", "feature")
    commit_files(repo, paths, "feature")
    git(repo, "switch", "master")
    commit_files(repo, ["unrelated.txt"], "master moved on")
    git(repo, "merge", "--no-ff", "-m", "merge", "feature")


def run(
    repo: Path,
    workflow: str,
    event: str,
    ref: str,
    before: str = "",
    fork: bool = False,
) -> dict:
    out = subprocess.run(
        [sys.executable, str(SCRIPT), workflow],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={
            "EVENT_NAME": event,
            "REF": ref,
            "BEFORE_SHA": before,
            "HEAD_FORK": str(fork).lower(),
            "PATH": "/usr/bin:/bin",
        },
    )
    return dict(line.split("=") for line in out.stdout.splitlines())


DOCS_ONLY = [
    ["readme.md"],
    ["docs/release.md", "docs/new/page.md"],
    ["apps/web/readme.md"],
]
CODE = [
    ["packages/tsdhn/tsdhn/pipeline/stage.py"],
    ["readme.md", "apps/web/src/lib/page.ts"],
    ["docs/release.md", "uv.lock"],
]


@pytest.mark.parametrize("paths", DOCS_ONLY)
def test_pull_request_that_changes_only_docs_skips_the_code_checks(repo, paths):
    merge_pull_request(repo, paths)
    assert run(repo, "ci", "pull_request", "refs/pull/1/merge") == {
        "code": "false",
        "docs": "true",
    }


@pytest.mark.parametrize("paths", CODE)
def test_pull_request_that_changes_code_runs_the_code_checks(repo, paths):
    merge_pull_request(repo, paths)
    assert run(repo, "ci", "pull_request", "refs/pull/1/merge") == {
        "code": "true",
        "docs": "false",
    }


@pytest.mark.parametrize("event", ["push", "merge_group", "workflow_dispatch"])
def test_other_events_run_the_code_checks_even_for_docs(repo, event):
    commit_files(repo, ["docs/release.md"], "docs")
    before = git(repo, "rev-parse", "HEAD^")
    assert run(repo, "ci", event, "refs/heads/master", before)["code"] == "true"


IMAGE_PATHS = [
    ["deploy/api.Dockerfile"],
    ["deploy/backup/tsdhn-backup"],
    [".devcontainer/Dockerfile"],
    ["uv.lock"],
    ["bun.lock"],
    ["mise.toml"],
    ["docker-compose.yml"],
    ["pyproject.toml"],
    ["packages/api/pyproject.toml"],
    ["model/grid/depth.dat"],
    ["apps/web/package.json"],
    ["apps/web/vite.config.ts"],
    ["scripts/e2e/compute_stack_smoke.sh"],
    [".github/workflows/release.yml"],
    [".github/release-notes.md"],
    ["docs/release.md", ".github/release-notes.md"],
]
NO_IMAGE_PATHS = [
    ["readme.md"],
    ["packages/api/api/main.py"],
    ["packages/tsdhn/tsdhn/pipeline/stage.py"],
    ["apps/web/src/routes/+page.svelte"],
    [".github/workflows/ci.yml"],
]


@pytest.mark.parametrize("paths", IMAGE_PATHS)
def test_pull_request_that_changes_an_image_input_builds_the_images(repo, paths):
    merge_pull_request(repo, paths)
    assert run(repo, "release", "pull_request", "refs/pull/1/merge") == {
        "release": "true",
        "images": "true",
        "warm": "false",
    }


def test_fork_pull_request_that_changes_an_image_input_builds_no_images(repo):
    merge_pull_request(repo, ["uv.lock"])
    assert run(repo, "release", "pull_request", "refs/pull/1/merge", fork=True) == {
        "release": "true",
        "images": "false",
        "warm": "false",
    }


@pytest.mark.parametrize("paths", NO_IMAGE_PATHS)
def test_pull_request_that_changes_no_image_input_keeps_only_the_cheap_jobs(
    repo, paths
):
    merge_pull_request(repo, paths)
    assert run(repo, "release", "pull_request", "refs/pull/1/merge") == {
        "release": "true",
        "images": "false",
        "warm": "false",
    }


@pytest.mark.parametrize(
    ("event", "ref"),
    [("workflow_dispatch", "refs/heads/feature"), ("push", "refs/tags/v1.2.3")],
)
def test_manual_and_tag_runs_always_build_the_images(repo, event, ref):
    commit_files(repo, ["readme.md"], "docs")
    assert run(repo, "release", event, ref, ZEROS) == {
        "release": "true",
        "images": "true",
        "warm": "false",
    }


def test_master_push_warms_the_caches_only_when_an_image_input_changed(repo):
    commit_files(repo, ["deploy/web.Dockerfile"], "image input")
    before = git(repo, "rev-parse", "HEAD^")
    expected = {"release": "false", "images": "false", "warm": "true"}
    assert run(repo, "release", "push", "refs/heads/master", before) == expected

    commit_files(repo, ["docs/release.md"], "docs")
    before = git(repo, "rev-parse", "HEAD^")
    expected = {"release": "false", "images": "false", "warm": "false"}
    assert run(repo, "release", "push", "refs/heads/master", before) == expected


def test_master_push_without_a_base_warms_the_caches(repo):
    commit_files(repo, ["docs/release.md"], "docs")
    expected = {"release": "false", "images": "false", "warm": "true"}
    assert run(repo, "release", "push", "refs/heads/master", ZEROS) == expected


def test_master_push_sees_every_commit_since_the_previous_head(repo):
    before = git(repo, "rev-parse", "HEAD")
    commit_files(repo, ["uv.lock"], "lock")
    commit_files(repo, ["docs/release.md"], "docs")
    assert run(repo, "release", "push", "refs/heads/master", before)["warm"] == "true"
