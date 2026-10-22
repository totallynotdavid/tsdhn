import math
from typing import Any

import numpy as np
import pytest

from tsdhn_ttt import Bathymetry, locate_source, read_bathymetry, travel_times
from tsdhn_ttt.solver import EARTH_RADIUS_M

from .conftest import WriteI2

BIAS = math.sqrt(math.sin(2 * math.pi / 120) / (2 * math.pi / 120))
G_EQUATOR = 9.7803267715


def _bathymetry(write_i2: WriteI2, depth: np.ndarray, **kwargs: Any) -> Bathymetry:
    return read_bathymetry(write_i2(depth, **kwargs))


def test_open_ocean_row_matches_depth_speed(
    write_i2: WriteI2, ocean: np.ndarray
) -> None:
    b = _bathymetry(write_i2, ocean, y_max=1.0)
    source_row, source_col, steps = 10, 4, 12
    lat = 1.0 - source_row * 0.1
    lon, lat_source = 0.4, 0.0

    result = travel_times(b, lon, lat_source)

    metres = steps * math.radians(0.1) * EARTH_RADIUS_M * math.cos(math.radians(lat))
    seconds = metres / math.sqrt(G_EQUATOR * 4000.0)
    assert result.hours[source_row, source_col] == pytest.approx(0.0, abs=1e-12)
    assert result.hours[source_row, source_col + steps] * 3600.0 == pytest.approx(
        seconds * BIAS, rel=1e-4
    )


def test_source_slope_is_the_inverse_speed(
    write_i2: WriteI2, ocean: np.ndarray
) -> None:
    b = _bathymetry(write_i2, ocean)

    result = travel_times(b, 1.5, 0.0)

    expected = 1000.0 / math.sqrt(G_EQUATOR * 4000.0) * BIAS
    assert result.source_slope_s_per_km == pytest.approx(expected, rel=0.02)


def test_wall_with_a_gap_delays_the_far_side(
    write_i2: WriteI2, ocean: np.ndarray
) -> None:
    depth = ocean.copy()
    depth[:, 15] = 100
    depth[2, 15] = -4000
    b = _bathymetry(write_i2, depth)

    walled = travel_times(b, 0.5, 0.0)
    open_sea = travel_times(_bathymetry(write_i2, ocean, name="open.i2"), 0.5, 0.0)

    assert np.isnan(walled.hours[:, 15][np.arange(21) != 2]).all()
    behind = walled.hours[10, 18]
    assert behind > open_sea.hours[10, 18] * 1.2
    assert behind < 2 * open_sea.hours[10, 18]


def test_enclosed_water_is_not_reached(write_i2: WriteI2, ocean: np.ndarray) -> None:
    depth = ocean.copy()
    depth[8:13, 20:25] = 50
    depth[10, 22] = -300
    b = _bathymetry(write_i2, depth)

    result = travel_times(b, 0.5, 0.0)

    assert result.unreached == 1
    assert np.isnan(result.hours[10, 22])
    assert np.isnan(result.hours[8, 20])
    assert not np.isnan(result.hours[10, 19])


def test_shallower_water_is_slower(write_i2: WriteI2, ocean: np.ndarray) -> None:
    shelf = ocean.copy()
    shelf[:, 10:] = -50
    b = _bathymetry(write_i2, shelf)
    deep = _bathymetry(write_i2, ocean, name="deep.i2")

    on_shelf = travel_times(b, 0.5, 0.0)
    in_deep = travel_times(deep, 0.5, 0.0)

    assert on_shelf.hours[10, 20] > 3 * in_deep.hours[10, 20]
    assert on_shelf.maximum_hours > in_deep.maximum_hours


def test_land_epicenter_is_an_error(write_i2: WriteI2, ocean: np.ndarray) -> None:
    depth = ocean.copy()
    depth[10, 4] = 10
    b = _bathymetry(write_i2, depth)

    with pytest.raises(ValueError, match="land"):
        travel_times(b, 0.4, 0.0)


@pytest.mark.parametrize(("lon", "lat"), [(3.5, 0.0), (-0.5, 0.0), (1.0, 1.5)])
def test_epicenter_outside_the_grid_is_an_error(
    write_i2: WriteI2, ocean: np.ndarray, lon: float, lat: float
) -> None:
    b = _bathymetry(write_i2, ocean)

    with pytest.raises(ValueError, match="outside"):
        travel_times(b, lon, lat)


def test_global_grid_is_rejected(write_i2: WriteI2) -> None:
    depth = np.full((5, 37), -4000, dtype=np.int16)
    b = _bathymetry(write_i2, depth, step=10.0, y_max=20.0)

    with pytest.raises(ValueError, match="360"):
        travel_times(b, 5.0, 10.0)


def test_negative_longitude_is_read_east_of_the_date_line(
    write_i2: WriteI2, ocean: np.ndarray
) -> None:
    b = _bathymetry(write_i2, ocean, x_min=178.0)

    assert locate_source(b, -179.5, 0.0) == locate_source(b, 180.5, 0.0) == (10, 25)


def test_epicenter_between_nodes_starts_the_wavefront_at_the_epicenter(
    write_i2: WriteI2, ocean: np.ndarray
) -> None:
    b = _bathymetry(write_i2, ocean)
    metres_per_degree = math.radians(1.0) * EARTH_RADIUS_M
    speed = math.sqrt(G_EQUATOR * 4000.0)

    result = travel_times(b, 0.43, 0.0)

    assert result.hours.dtype == np.float64
    # Both nodes lie on the epicenter's row, so the straight segment is exact
    # and only float64 rounding is left.
    assert result.hours[10, 4] * 3600.0 == pytest.approx(
        0.03 * metres_per_degree / speed * BIAS, rel=1e-9
    )
    assert result.hours[10, 5] * 3600.0 == pytest.approx(
        0.07 * metres_per_degree / speed * BIAS, rel=1e-9
    )


def test_client_compatible_mode_starts_at_the_nearest_node_in_float32(
    write_i2: WriteI2, ocean: np.ndarray
) -> None:
    b = _bathymetry(write_i2, ocean)

    result = travel_times(b, 0.43, 0.0, client_compatible=True)

    assert result.hours.dtype == np.float32
    assert result.hours[10, 4] == 0.0
    assert result.hours[10, 5] > 0.0


def test_epicenter_start_does_not_cross_land(
    write_i2: WriteI2, ocean: np.ndarray
) -> None:
    wall = ocean.copy()
    wall[:, 6] = 100
    wall[2, 6] = -4000
    walled = _bathymetry(write_i2, wall)
    open_sea = _bathymetry(write_i2, ocean, name="open.i2")

    behind = travel_times(walled, 0.53, 0.0).hours[10, 8]
    direct = travel_times(open_sea, 0.53, 0.0).hours[10, 8]

    # The wall leaves one opening, at 0.6/0.8. A path through it, even half a
    # cell (0.05 degrees) closer to the epicenter's row, is the two legs below
    # long, against 0.27 degrees straight. The sphere shortens a leg by less
    # than 1e-3 at these latitudes.
    detour = (math.hypot(0.07, 0.75) + math.hypot(0.2, 0.75)) / 0.27
    assert behind >= (1.0 - 1e-3) * detour * direct
