"""Compare `tsdhn_ttt` with the compiled `ttt_client` on the same grid.

The client comes from `TSDHN_TOOLS_DIR`, `PATH`, or the toolchain Docker image.
Tests skip when none is available. Float32 path sums can differ by rounding by
about one second over a few thousand hops, so the 0.02-minute tolerance covers
arithmetic differences while larger differences indicate a method mismatch.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from tsdhn_parity import (
    Case,
    Checkpoint,
    Tolerance,
    Trace,
    UnitSpec,
    assert_parity,
    parity_cases,
)
from tsdhn_ttt import read_bathymetry, travel_times
from tsdhn_ttt.grid import HEADER_SIZE, Bathymetry

from .conftest import write_depth_grid

CORTADO = Path(__file__).resolve().parents[3] / "model" / "ttt_mundo" / "cortado.i2"
TOOLCHAIN_IMAGE = os.environ.get(
    "TSDHN_TOOLCHAIN_IMAGE", "ghcr.io/totallynotdavid/tsdhn-toolchain:master"
)
ARRIVAL_TOLERANCE_MINUTES = 0.02


def _client_command(workdir: Path) -> list[str] | None:
    """Return the argv prefix that runs `ttt_client` in `workdir`, or None."""
    tools_dir = os.environ.get("TSDHN_TOOLS_DIR")
    if tools_dir and (Path(tools_dir) / "ttt_client").is_file():
        return [str(Path(tools_dir).resolve() / "ttt_client")]
    on_path = shutil.which("ttt_client")
    if on_path:
        return [on_path]
    docker = shutil.which("docker")
    if docker is None:
        return None
    probe = subprocess.run(  # noqa: S603
        [docker, "image", "inspect", TOOLCHAIN_IMAGE],
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    return [
        docker,
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{workdir}:/work",
        "-w",
        "/work",
        TOOLCHAIN_IMAGE,
        "ttt_client",
    ]


def _shelf_with_island(node_offset: int) -> Bathymetry:
    """Open ocean with a shallow shelf, a ridge with a gap and an island."""
    ny, nx = 90, 120
    depth = np.full((ny, nx), -4000.0, dtype=np.float32)
    depth[:, :30] = -60.0
    depth[:, 30:40] = np.linspace(-60.0, -4000.0, 10, dtype=np.float32)
    depth[40:60, 80:84] = np.nan
    depth[48:52, 80:84] = -300.0
    depth[10:25, 95:110] = np.nan
    step = 0.1
    span = 1 - node_offset
    return Bathymetry(
        x_min=150.0,
        x_max=150.0 + (nx - span) * step,
        y_min=-20.0 - (ny - span) * step,
        y_max=-20.0,
        node_offset=node_offset,
        depth=depth,
    )


def _grid(name: str) -> Bathymetry:
    if name == "cortado":
        return read_bathymetry(CORTADO)
    return _shelf_with_island(node_offset=int(name.removeprefix("shelf_offset")))


def _trace(case: Case, hours: np.ndarray) -> Trace:
    reached = ~np.isnan(hours)
    arrival_minutes = np.where(reached, hours.astype(np.float64) * 60.0, 0.0)
    return Trace(
        case_id=case.id,
        checkpoints=(
            Checkpoint.of("reached", reached.astype(np.int8)),
            Checkpoint.of("arrival_minutes", arrival_minutes),
        ),
    )


def _epicenter(case: Case) -> tuple[float, float]:
    return float(case.params["lon"]), float(case.params["lat"])


class ClientAdapter:
    """Run the compiled `ttt_client` and read the `.b` grid it writes."""

    def run(self, case: Case) -> Trace:
        with tempfile.TemporaryDirectory(prefix="tsdhn-ttt-") as raw_dir:
            workdir = Path(raw_dir)
            command = _client_command(workdir)
            if command is None:
                pytest.skip(
                    "requires ttt_client on PATH, TSDHN_TOOLS_DIR, "
                    f"or the Docker image {TOOLCHAIN_IMAGE}"
                )
            bathymetry = _grid(str(case.params["grid"]))
            write_depth_grid(workdir / "grid.i2", bathymetry)
            lon, lat = _epicenter(case)
            subprocess.run(  # noqa: S603
                [*command, "grid.i2", f"-E{lon:.2f}/{lat:.2f}", "-Tttt.b", "-VL"],
                cwd=workdir,
                capture_output=True,
                check=True,
            )
            hours = np.fromfile(
                workdir / "ttt.b", dtype="<f4", offset=HEADER_SIZE
            ).reshape(bathymetry.depth.shape)
        return _trace(case, hours)


class PackageAdapter:
    """Run `tsdhn_ttt` in its `ttt_client`-compatible mode on the same case."""

    def run(self, case: Case) -> Trace:
        lon, lat = _epicenter(case)
        result = travel_times(
            _grid(str(case.params["grid"])), lon, lat, client_compatible=True
        )
        return _trace(case, result.hours)


def _spec(cases: list[Case]) -> UnitSpec:
    return UnitSpec(
        id="ttt",
        cases=cases,
        legacy=ClientAdapter(),
        python=PackageAdapter(),
        tolerances={
            "reached": Tolerance(rtol=0.0, atol=0.0),
            "arrival_minutes": Tolerance(rtol=0.0, atol=ARRIVAL_TOLERANCE_MINUTES),
        },
    )


SYNTHETIC = _spec(
    [
        Case(
            id=f"shelf_offset{offset}",
            params={"grid": f"shelf_offset{offset}", "lon": 151.0, "lat": -25.0},
        )
        for offset in (0, 1)
    ]
)

EPICENTERS = {
    "trench_5s": (-82.00, -5.00),
    "trench_10s": (-80.20, -10.00),
    "trench_15s": (-76.50, -15.00),
    "trench_20s": (-71.40, -20.00),
    "trench_25s": (-71.47, -25.00),
    "trench_30s": (-72.47, -30.00),
    "trench_35s": (-73.73, -35.00),
    "japan": (142.40, 38.30),
    "alaska": (-149.00, 56.00),
}
CORTADO_SPEC = _spec(
    [
        Case(id=name, params={"grid": "cortado", "lon": lon, "lat": lat})
        for name, (lon, lat) in EPICENTERS.items()
    ]
)


@pytest.mark.parametrize("case", parity_cases(SYNTHETIC))
def test_synthetic_grid_matches_client(case: Case) -> None:
    assert_parity(SYNTHETIC, case)


@pytest.mark.golden
@pytest.mark.parametrize("case", parity_cases(CORTADO_SPEC))
def test_cortado_grid_matches_client(case: Case) -> None:
    if os.environ.get("NUMBA_DISABLE_JIT", "0") != "0":
        pytest.skip("the world grid needs the compiled kernel (NUMBA_DISABLE_JIT=0)")
    assert_parity(CORTADO_SPEC, case)
