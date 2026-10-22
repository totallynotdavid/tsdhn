import struct
from pathlib import Path

import numpy as np
import pytest

from tsdhn_ttt import read_bathymetry, write_travel_times
from tsdhn_ttt.grid import HEADER_SIZE

from .conftest import WriteI2


def test_read_marks_no_data_as_nan(write_i2: WriteI2) -> None:
    depth = np.array([[-100, -32768, 25], [32767, -1, -5000]], dtype=np.int16)

    bathymetry = read_bathymetry(write_i2(depth))

    assert np.isnan(bathymetry.depth[0, 1])
    assert np.isnan(bathymetry.depth[1, 0])
    assert bathymetry.depth[0, 0] == -100
    assert bathymetry.depth[0, 2] == 25
    assert bathymetry.depth[1, 2] == -5000


@pytest.mark.parametrize(("node_offset", "x_inc"), [(0, 0.1), (1, 0.1)])
def test_increments_follow_registration(
    write_i2: WriteI2, ocean: np.ndarray, node_offset: int, x_inc: float
) -> None:
    bathymetry = read_bathymetry(write_i2(ocean, node_offset=node_offset))

    assert bathymetry.x_inc == pytest.approx(x_inc)
    assert bathymetry.y_inc == pytest.approx(0.1)


def test_truncated_grid_is_rejected(write_i2: WriteI2, ocean: np.ndarray) -> None:
    path = write_i2(ocean)
    path.write_bytes(path.read_bytes()[:-2])

    with pytest.raises(ValueError, match="expected"):
        read_bathymetry(path)


def test_written_grid_holds_float_hours_and_the_header(
    write_i2: WriteI2, ocean: np.ndarray, tmp_path: Path
) -> None:
    bathymetry = read_bathymetry(write_i2(ocean))
    hours = np.linspace(0.0, 5.0, ocean.size, dtype=np.float32).reshape(ocean.shape)
    hours[0, 0] = np.nan
    out = tmp_path / "ttt.b"

    write_travel_times(out, bathymetry, hours, (-78.8, -12.0), 4.88)

    raw = out.read_bytes()
    nx, ny, node_offset, x_min, x_max, y_min, y_max, z_min, z_max, *_ = (
        struct.unpack_from("<3i10d", raw)
    )
    assert (nx, ny, node_offset) == (30, 21, 0)
    assert (x_min, x_max) == pytest.approx((0.0, 2.9))
    assert (y_min, y_max) == pytest.approx((-1.0, 1.0))
    assert z_min == pytest.approx(float(np.nanmin(hours)))
    assert z_max == pytest.approx(5.0)
    assert b"-78.8 -12 0 0 0 0 0 0 4.88 " in raw[:HEADER_SIZE]
    stored = np.frombuffer(raw, dtype="<f4", offset=HEADER_SIZE).reshape(hours.shape)
    np.testing.assert_array_equal(stored, hours)
