from pathlib import Path

import numpy as np
import pytest

from tsdhn.calculator import TsunamiCalculator, nearest_focal_mechanism
from tsdhn.domain import EarthquakeInput
from tsdhn.fault_plane import run_fault_plane
from tsdhn.utils.file_utils import prepare_simulation_workspace
from tsdhn.utils.geo import to_0_360

MODEL_DIR = Path(__file__).resolve().parents[3] / "model"


def test_to_0_360_shifts_only_negative_longitudes() -> None:
    assert to_0_360(-156.0) == pytest.approx(204.0)
    assert to_0_360(156.0) == pytest.approx(156.0)
    assert to_0_360(0.0) == pytest.approx(0.0)


def test_nearest_mechanism_matches_real_mecfoc_alaska_1964() -> None:
    mecfoc = np.loadtxt(MODEL_DIR / "mecfoc.dat")
    assert nearest_focal_mechanism(mecfoc, -156.0, 56.0) == pytest.approx((247.0, 8.0))
    assert nearest_focal_mechanism(mecfoc, 204.0, 56.0) == pytest.approx((247.0, 8.0))


# Columns: lon, lat, strike, dip. One mechanism sits just east of the
# antimeridian (-179.0 is 181.0) and one just west of it.
_ACROSS_ANTIMERIDIAN = np.array(
    [
        [171.0, 0.0, 10.0, 11.0],
        [-179.0, 0.0, 20.0, 21.0],
    ]
)


@pytest.mark.parametrize(
    ("lon", "expected"),
    [
        (170.0, (10.0, 11.0)),
        (-190.0, (10.0, 11.0)),
        (179.0, (20.0, 21.0)),
        (-179.5, (20.0, 21.0)),
        (-179.0, (20.0, 21.0)),
    ],
)
def test_nearest_mechanism_treats_the_antimeridian_as_continuous(
    lon: float, expected: tuple[float, float]
) -> None:
    assert nearest_focal_mechanism(_ACROSS_ANTIMERIDIAN, lon, 0.0) == expected


@pytest.mark.parametrize(
    ("lat0", "lon0"),
    [(56.0, -156.0), (36.0, 142.0), (52.0, 179.9), (52.0, -179.9), (-20.0, -175.0)],
)
def test_preview_and_simulation_use_the_same_mechanism(
    tmp_path: Path, lat0: float, lon0: float
) -> None:
    data = EarthquakeInput(Mw=8.5, h=20.0, lat0=lat0, lon0=lon0, hhmm="0000", dia="01")
    prepare_simulation_workspace(MODEL_DIR, tmp_path)

    preview = TsunamiCalculator(MODEL_DIR).calculate_earthquake_parameters(
        data, tmp_path
    )
    run_fault_plane(tmp_path)

    tokens = (tmp_path / "pfalla.inp").read_text().split()
    assert (preview.azimuth, preview.dip) == pytest.approx(
        (float(tokens[5]), float(tokens[6]))
    )


def test_nearest_mechanism_treats_the_greenwich_meridian_as_continuous() -> None:
    mecfoc = np.array([[1.0, 0.0, 10.0, 11.0], [350.0, 0.0, 20.0, 21.0]])
    assert nearest_focal_mechanism(mecfoc, 359.0, 0.0) == (10.0, 11.0)
    assert nearest_focal_mechanism(mecfoc, -1.0, 0.0) == (10.0, 11.0)
    assert nearest_focal_mechanism(mecfoc, 352.0, 0.0) == (20.0, 21.0)


def test_preview_and_simulation_pick_the_mechanism_across_greenwich(
    tmp_path: Path,
) -> None:
    """Mechanisms at 1 and 350 E, epicenter at 359 E: the one 2 degrees away."""
    # The Pacific model grid ends at 292 E, so the run gets a grid around 359 E.
    model = tmp_path / "model"
    (model / "bathy").mkdir(parents=True)
    for entry in MODEL_DIR.iterdir():
        if entry.name not in ("mecfoc.dat", "bathy"):
            (model / entry.name).symlink_to(entry)
    for entry in (MODEL_DIR / "bathy").iterdir():
        (model / "bathy" / entry.name).symlink_to(entry)
    for name in ("mecfoc.dat", "bathy/xa.dat", "bathy/ya.dat"):
        (model / name).unlink(missing_ok=True)
    (model / "mecfoc.dat").write_text("1.0 0.0 100.0 20.0\n350.0 0.0 200.0 30.0\n")
    np.savetxt(model / "bathy/xa.dat", np.arange(340.0, 380.0, 0.1))
    np.savetxt(model / "bathy/ya.dat", np.arange(-10.0, 10.0, 0.1))

    data = EarthquakeInput(Mw=8.0, h=20.0, lat0=0.0, lon0=-1.0, hhmm="0000", dia="01")
    workspace = tmp_path / "run"
    prepare_simulation_workspace(model, workspace)

    preview = TsunamiCalculator(model).calculate_earthquake_parameters(data, workspace)
    run_fault_plane(workspace)

    tokens = (workspace / "pfalla.inp").read_text().split()
    assert (preview.azimuth, preview.dip) == (100.0, 20.0)
    assert (float(tokens[5]), float(tokens[6])) == (100.0, 20.0)
