from pathlib import Path

import numpy as np
import pytest
from pygmt.enums import GridRegistration, GridType

from tsdhn.pipeline.types import ProcessingStep, ToolRunner
from tsdhn.render.maxola import GridConfig, load_stations, process_grid
from tsdhn.runtime import (
    REQUIRED_MODEL_FILES,
    REQUIRED_TOOL_EXECUTABLES,
    RuntimeContext,
)
from tsdhn.utils.file_utils import (
    WORKSPACE_DIRS,
    WORKSPACE_INPUTS,
    prepare_simulation_workspace,
)
from tsdhn.utils.processing import process_step


def _create_model_dir(root: Path) -> Path:
    model_dir = root / "model"
    model_dir.mkdir()
    for dirname in WORKSPACE_DIRS:
        (model_dir / dirname).mkdir()
    for relative_name in REQUIRED_MODEL_FILES:
        path = model_dir / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative_name}\n", encoding="utf-8")
    return model_dir


def _create_tools_dir(root: Path) -> Path:
    tools_dir = root / "tools"
    tools_dir.mkdir()
    for executable in REQUIRED_TOOL_EXECUTABLES:
        path = tools_dir / executable
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    return tools_dir


def test_runtime_context_reports_missing_managed_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TSDHN_MODEL_DIR", raising=False)
    monkeypatch.delenv("TSDHN_TOOLS_DIR", raising=False)
    monkeypatch.setenv("TSDHN_DATA_HOME", str(tmp_path / "missing"))

    with pytest.raises(RuntimeError, match="tsdhn assets install"):
        RuntimeContext.resolve(require_tools=False)


def test_runtime_paths_resolve_explicit_paths(tmp_path: Path) -> None:
    model_dir = _create_model_dir(tmp_path)
    tools_dir = _create_tools_dir(tmp_path)

    runtime = RuntimeContext.resolve(model_dir=model_dir, tools_dir=tools_dir)

    assert runtime.model_dir == model_dir.resolve()
    assert runtime.tools_dir == tools_dir.resolve()


def test_runtime_paths_can_resolve_model_only_when_no_tools_are_needed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = _create_model_dir(tmp_path)
    monkeypatch.delenv("TSDHN_TOOLS_DIR", raising=False)

    runtime = RuntimeContext.resolve(model_dir=model_dir, require_tools=False)

    assert runtime.model_dir == model_dir.resolve()
    assert runtime.tools_dir is None


def test_runtime_paths_validate_only_required_tools(tmp_path: Path) -> None:
    model_dir = _create_model_dir(tmp_path)
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    executable = tools_dir / "fault_plane"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    runtime = RuntimeContext.resolve(
        model_dir=model_dir,
        tools_dir=tools_dir,
        required_tools=("fault_plane",),
    )

    assert runtime.tools_dir == tools_dir.resolve()


def test_runtime_paths_validate_only_required_tools_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = _create_model_dir(tmp_path)
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    executable = tools_dir / "fault_plane"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("TSDHN_TOOLS_DIR", str(tools_dir))

    runtime = RuntimeContext.resolve(
        model_dir=model_dir,
        required_tools=("fault_plane",),
    )

    assert runtime.tools_dir == tools_dir.resolve()


def test_prepare_simulation_workspace_links_only_required_inputs(
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "work"
    model_dir = _create_model_dir(tmp_path)

    generated_seed = model_dir / "zfolder" / "green.dat"
    generated_seed.write_text("stale generated output\n", encoding="utf-8")

    work_dir.mkdir()
    (work_dir / "old.txt").write_text("old workspace\n", encoding="utf-8")

    prepare_simulation_workspace(model_dir, work_dir)

    assert not (work_dir / "old.txt").exists()
    for dirname in WORKSPACE_DIRS:
        assert (work_dir / dirname).is_dir()
    for relative_name in WORKSPACE_INPUTS:
        assert (work_dir / relative_name).is_file()

    assert not (work_dir / "zfolder" / "green.dat").exists()


def test_load_stations_uses_package_resource(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    stations = load_stations()

    assert {station.code for station in stations if station.active} == {
        "TALA",
        "CALL",
        "MATA",
    }


def test_process_grid_returns_pixel_registered_dataarray(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    zfolder = work_dir / "zfolder"
    zfolder.mkdir(parents=True)
    np.savetxt(zfolder / "zmax_a.grd", np.arange(12, dtype=np.float32))

    grid_config = GridConfig(ncols=4, nrows=3, dx=111.1994)
    grid = process_grid(work_dir, grid_config)

    assert grid.dims == ("lat", "lon")
    assert grid.shape == (3, 4)
    assert grid.gmt.registration is GridRegistration.PIXEL
    assert grid.gmt.gtype is GridType.GEOGRAPHIC
    assert grid.lon.to_numpy().tolist() == pytest.approx(
        [128.02827778, 128.02927778, 128.03027778, 128.03127778]
    )
    assert grid.lat.to_numpy().tolist() == pytest.approx(
        [-76.00505556, -76.00405556, -76.00305556]
    )
    np.testing.assert_allclose(
        grid.to_numpy(),
        np.array(
            [
                [0.0, 1.09, 2.18, 3.27],
                [4.36, 5.45, 6.55, 7.64],
                [8.73, 9.82, 10.91, 12.0],
            ],
            dtype=np.float32,
        ),
    )


def test_process_step_uses_prebuilt_executable(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    work_dir = tmp_path / "work"
    tools_dir.mkdir()
    work_dir.mkdir()

    executable = tools_dir / "hello"
    executable.write_text("#!/bin/sh\necho ok > ran.txt\n", encoding="utf-8")
    executable.chmod(0o755)

    process_step(
        ProcessingStep(
            name="hello",
            outputs=("ran.txt",),
            runner=ToolRunner("hello"),
            file_checks=(("ran.txt", "prebuilt executable did not run"),),
        ),
        work_dir,
        tools_dir,
    )

    assert (work_dir / "ran.txt").read_text(encoding="utf-8").strip() == "ok"
