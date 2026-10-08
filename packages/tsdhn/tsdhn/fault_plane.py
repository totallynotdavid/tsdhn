"""Fault placement and file-format port of `model/fault_plane.f90`."""

import math
from pathlib import Path

import numpy as np

from tsdhn.calculator import (
    average_slip,
    calculate_rectangle_parameters,
    nearest_focal_mechanism,
    rupture_dimensions,
)
from tsdhn.constants import FAULT_PLANE_KILOMETERS_PER_DEGREE
from tsdhn.utils.file_utils import atomic_write
from tsdhn.utils.geo import to_0_360

_RAKE = 90.0


def _read_hypo_dat(path: Path) -> tuple[str, float, float, float, float]:
    """Read the five fields consumed by the legacy fault-plane step."""
    lines = path.read_text().splitlines()
    hhmm = lines[0].strip()
    lon0 = float(lines[1])
    lat0 = float(lines[2])
    zep_km = float(lines[3])
    mw = float(lines[4])
    return hhmm, lon0, lat0, zep_km, mw


def _grid_snap(
    xa: np.ndarray, ya: np.ndarray, xo_grid: float, yo: float
) -> tuple[int, int]:
    """Return 1-based indices for the nearest bathymetry cells."""
    i0 = int(np.argmin(np.abs(xa - xo_grid))) + 1
    j0 = int(np.argmin(np.abs(ya - yo))) + 1
    return i0, j0


def _grid_window(
    xa: np.ndarray, ya: np.ndarray, xep: float, yep: float, l_km: float, mw: float
) -> tuple[int, int, int, int]:
    """Return the deformation window in full-grid indices."""
    cte = 1.4 if mw > 8.0 else 2.8
    off = cte * l_km / FAULT_PLANE_KILOMETERS_PER_DEGREE
    # The Fortran assignment truncates each geographic bound before snapping.
    ids = int(np.argmin(np.abs(xa - int(xep - off)))) + 1
    ide = int(np.argmin(np.abs(xa - int(xep + off)))) + 1
    jds = int(np.argmin(np.abs(ya - int(yep - off)))) + 1
    jde = int(np.argmin(np.abs(ya - int(yep + off)))) + 1
    return ids, ide, jds, jde


def _recompute_depth(
    lon0: float, lat0: float, xo: float, yo: float, zep_km: float, az: float, dip: float
) -> float:
    """Compute the fault's upper-edge depth in meters."""
    delta_x = (lon0 - xo) * FAULT_PLANE_KILOMETERS_PER_DEGREE
    delta_y = (lat0 - yo) * FAULT_PLANE_KILOMETERS_PER_DEGREE
    h = zep_km - (
        delta_x * math.cos(math.radians(-az)) + delta_y * math.sin(math.radians(-az))
    ) * math.tan(math.radians(dip))
    h_m = h * 1000.0
    if h_m < 0:
        # The active Fortran reference substitutes 5000 m for a negative depth.
        h_m = 5000.0
    return h_m


def _write_pfalla_inp(
    path: Path,
    i0: int,
    j0: int,
    d0_m: float,
    l0_m: float,
    w0_m: float,
    az: float,
    dip: float,
    rake: float,
    h_m: float,
) -> None:
    """Write the whitespace-separated fault geometry in meters."""
    with atomic_write(path) as tmp_path:
        tmp_path.write_text(f"{i0} {j0} {d0_m} {l0_m} {w0_m} {az} {dip} {rake} {h_m}\n")


def _write_xyo_dat(path: Path, ids: int, ide: int, jds: int, jde: int) -> None:
    """Write the deformation window as four 1-based grid indices."""
    with atomic_write(path) as tmp_path:
        tmp_path.write_text(f"{ids} {ide} {jds} {jde}\n")


def _write_meca_dat(
    path: Path,
    xep: float,
    lat0: float,
    zep_km: float,
    az: float,
    dip: float,
    mw: float,
    hhmm: str,
    rake: float = _RAKE,
) -> None:
    """Write the legacy fixed-width `meca.dat` record."""
    fields = "".join(f"{v:7.2f}" for v in (xep, lat0, zep_km, az, dip, rake, mw))
    with atomic_write(path) as tmp_path:
        tmp_path.write_text(f"{fields} 0 0 {hhmm}\n")


def run_fault_plane(working_dir: Path) -> None:
    """Read the workspace inputs and write the fault-plane files."""
    hhmm, lon0, lat0, zep_km, mw = _read_hypo_dat(working_dir / "hypo.dat")
    xep = to_0_360(lon0)

    l_km, w_km = rupture_dimensions(mw)
    _, dislocation_m = average_slip(mw, l_km, w_km)

    mecfoc = np.loadtxt(working_dir / "mecfoc.dat")
    az, dip = nearest_focal_mechanism(mecfoc, lon0, lat0)

    rect_params, _ = calculate_rectangle_parameters(l_km, w_km, lon0, lat0, az, dip)
    xo, yo = float(rect_params["xo"]), float(rect_params["yo"])

    xa = np.loadtxt(working_dir / "bathy/xa.dat")
    ya = np.loadtxt(working_dir / "bathy/ya.dat")

    if xep < xa[0]:
        raise RuntimeError(
            f"Epicenter is outside the computational grid (xep={xep} < xa[0]={xa[0]})"
        )

    xo_grid = to_0_360(xo)
    i0, j0 = _grid_snap(xa, ya, xo_grid, yo)
    h_m = _recompute_depth(lon0, lat0, xo, yo, zep_km, az, dip)

    _write_pfalla_inp(
        working_dir / "pfalla.inp",
        i0,
        j0,
        dislocation_m,
        l_km * 1000.0,
        w_km * 1000.0,
        az,
        dip,
        _RAKE,
        h_m,
    )

    ids, ide, jds, jde = _grid_window(xa, ya, xep, lat0, l_km, mw)
    _write_xyo_dat(working_dir / "xyo.dat", ids, ide, jds, jde)

    _write_meca_dat(working_dir / "meca.dat", xep, lat0, zep_km, az, dip, mw, hhmm)
