from pathlib import Path

import numpy as np
import pytest

from tsdhn.fault_plane import (
    _grid_window,
    _recompute_depth,
    _write_meca_dat,
    _write_pfalla_inp,
    _write_xyo_dat,
    run_fault_plane,
)
from tsdhn.utils.file_utils import prepare_simulation_workspace

MODEL_DIR = Path(__file__).resolve().parents[3] / "model"
TEST_DATA_DIR = Path(__file__).parent / "data"


def test_grid_window_truncates_target_before_snapping() -> None:
    # The legacy integer window truncates the target before snapping it to a
    # grid cell. A fine grid makes truncation distinguishable from rounding.
    xa = np.array([9.0, 10.0, 11.0, 12.0])
    ya = np.array([9.0, 10.0, 11.0, 12.0])
    ids, ide, jds, jde = _grid_window(xa, ya, xep=10.9, yep=10.9, l_km=0.0, mw=9.0)
    assert (ids, ide, jds, jde) == (2, 2, 2, 2)


def test_recompute_depth_clamps_negative_to_5000() -> None:
    h_m = _recompute_depth(
        lon0=-156.0, lat0=56.0, xo=-153.36, yo=56.42, zep_km=0.1, az=247.0, dip=8.0
    )
    assert h_m == pytest.approx(5000.0)


def test_write_pfalla_inp_is_nine_whitespace_tokens(tmp_path: Path) -> None:
    path = tmp_path / "pfalla.inp"
    _write_pfalla_inp(
        path, 1180, 1987, 11.96, 575439.9, 144543.9, 247.0, 8.0, 90.0, 1941.7
    )
    tokens = path.read_text().split()
    assert len(tokens) == 9
    assert int(tokens[0]) == 1180
    assert int(tokens[1]) == 1987


def test_write_xyo_dat_writes_the_four_window_indices(tmp_path: Path) -> None:
    path = tmp_path / "xyo.dat"
    _write_xyo_dat(path, 1021, 1246, 1861, 2056)
    assert path.read_text().split() == ["1021", "1246", "1861", "2056"]


def test_write_meca_dat_matches_real_captured_format(tmp_path: Path) -> None:
    path = tmp_path / "meca.dat"
    _write_meca_dat(path, 204.0, 56.0, 12.0, 247.0, 8.0, 9.0, "0000")
    real = (TEST_DATA_DIR / "meca.dat").read_text().strip()
    assert path.read_text().strip() == real


def test_run_fault_plane_matches_real_captured_alaska_1964(tmp_path: Path) -> None:
    prepare_simulation_workspace(MODEL_DIR, tmp_path)
    (tmp_path / "hypo.dat").write_text(
        "\n".join(["0000", "-156.00", "56.00", "12", "9.0"])
    )

    run_fault_plane(tmp_path)

    (
        real_i0,
        real_j0,
        real_slip,
        real_l,
        real_w,
        real_az,
        real_dip,
        real_rake,
        real_h,
    ) = (float(t) for t in (TEST_DATA_DIR / "pfalla.inp").read_text().split())
    (
        mine_i0,
        mine_j0,
        mine_slip,
        mine_l,
        mine_w,
        mine_az,
        mine_dip,
        mine_rake,
        mine_h,
    ) = (float(t) for t in (tmp_path / "pfalla.inp").read_text().split())
    assert mine_i0 == real_i0
    assert mine_j0 == real_j0
    assert mine_az == real_az
    assert mine_dip == real_dip
    assert mine_rake == real_rake
    np.testing.assert_allclose(
        [mine_slip, mine_l, mine_w, mine_h],
        [real_slip, real_l, real_w, real_h],
        rtol=2e-4,
    )

    assert (tmp_path / "xyo.dat").read_text().split() == [
        "1021",
        "1246",
        "1861",
        "2056",
    ]
    assert (tmp_path / "meca.dat").read_text().strip() == (
        TEST_DATA_DIR / "meca.dat"
    ).read_text().strip()


def test_run_fault_plane_rejects_an_epicenter_outside_the_grid(
    tmp_path: Path,
) -> None:
    prepare_simulation_workspace(MODEL_DIR, tmp_path)
    (tmp_path / "hypo.dat").write_text(
        "\n".join(["0000", "-156.00", "56.00", "12", "9.0"])
    )
    xa = tmp_path / "bathy" / "xa.dat"
    xa.unlink()
    xa.write_text("300.0\n301.0\n")

    with pytest.raises(RuntimeError, match="outside the computational grid"):
        run_fault_plane(tmp_path)
