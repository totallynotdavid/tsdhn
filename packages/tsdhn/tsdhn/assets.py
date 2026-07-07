import hashlib
import json
import os
import tarfile
import urllib.request
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, cast
from urllib.parse import urlparse

from tsdhn.runtime import REQUIRED_MODEL_DIRS, REQUIRED_MODEL_FILES, validate_model_dir

__all__ = [
    "DEFAULT_RELEASE_REPOSITORY",
    "ModelDataset",
    "ModelStore",
    "model_version_for_package",
]

DEFAULT_RELEASE_REPOSITORY = "totallynotdavid/tsdhn"


def model_version_for_package(package_version: str | None = None) -> str:
    return package_version or version("tsdhn")


@dataclass(frozen=True)
class ModelDataset:
    version: str
    path: Path
    managed: bool


class ModelStore:
    def __init__(
        self,
        root: Path | None = None,
        *,
        repository: str = DEFAULT_RELEASE_REPOSITORY,
    ) -> None:
        self.root = (root or _default_data_root()).expanduser().resolve()
        self.repository = repository

    def dataset_dir(self, model_version: str) -> Path:
        return self.root / "models" / model_version

    def resolve_installed(self, model_version: str) -> ModelDataset | None:
        path = self.dataset_dir(model_version)
        if not path.exists():
            return None
        return ModelDataset(
            version=model_version,
            path=validate_model_dir(path),
            managed=True,
        )

    def status(self, model_version: str) -> dict[str, Any]:
        path = self.dataset_dir(model_version)
        missing = _missing_model_entries(path)
        return {
            "version": model_version,
            "path": str(path),
            "installed": path.exists() and not missing,
            "missing": missing,
        }

    def install(
        self,
        model_version: str,
        *,
        url: str | None = None,
        sha256: str | None = None,
        force: bool = False,
    ) -> ModelDataset:
        target = self.dataset_dir(model_version)
        if target.exists() and not force:
            return ModelDataset(
                version=model_version,
                path=validate_model_dir(target),
                managed=True,
            )

        archive_url = url or self.release_asset_url(model_version)
        self.root.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(prefix="tsdhn-model-", suffix=".tar.gz") as tmp:
            _download(archive_url, Path(tmp.name))
            if sha256 is not None:
                _verify_sha256(Path(tmp.name), sha256)
            _extract_model_archive(Path(tmp.name), target)

        return ModelDataset(
            version=model_version,
            path=validate_model_dir(target),
            managed=True,
        )

    def release_asset_url(self, model_version: str) -> str:
        tag = f"v{model_version}"
        filename = f"tsdhn-model-v{model_version}.tar.gz"
        return (
            f"https://github.com/{self.repository}/releases/download/{tag}/{filename}"
        )


def _default_data_root() -> Path:
    if value := os.environ.get("TSDHN_DATA_HOME"):
        return Path(value)
    if value := os.environ.get("XDG_DATA_HOME"):
        return Path(value) / "tsdhn"
    return Path.home() / ".local" / "share" / "tsdhn"


def _missing_model_entries(path: Path) -> list[str]:
    missing_dirs = [
        f"{dirname}/"
        for dirname in REQUIRED_MODEL_DIRS
        if not (path / dirname).is_dir()
    ]
    missing_files = [
        filename for filename in REQUIRED_MODEL_FILES if not (path / filename).is_file()
    ]
    return missing_dirs + missing_files


def _download(url: str, destination: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Model downloads require an HTTPS URL")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        destination.write_bytes(response.read())


def _verify_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError(
            f"Model archive checksum mismatch: expected {expected}, got {digest}"
        )


def _extract_model_archive(archive: Path, target: Path) -> None:
    staging = target.with_name(f".{target.name}.tmp")
    if staging.exists():
        import shutil

        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(staging, filter="data")

    root = _find_model_root(staging)
    if target.exists():
        import shutil

        shutil.rmtree(target)
    root.rename(target)
    if staging.exists():
        import shutil

        shutil.rmtree(staging)


def _find_model_root(root: Path) -> Path:
    if not _missing_model_entries(root):
        return root
    candidates = [path for path in root.iterdir() if path.is_dir()]
    if len(candidates) == 1 and not _missing_model_entries(candidates[0]):
        return candidates[0]
    manifest = root / "manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("model_root"), str):
            model_root = cast(str, data["model_root"])
            candidate = root / model_root
            if not _missing_model_entries(candidate):
                return candidate
    raise RuntimeError(
        "Downloaded archive does not contain a valid TSDHN model dataset"
    )
