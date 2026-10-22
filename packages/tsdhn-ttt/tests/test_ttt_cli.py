import struct
from pathlib import Path

import numpy as np
import pytest

from tsdhn_ttt.__main__ import main
from tsdhn_ttt.grid import HEADER_SIZE

from .conftest import WriteI2


def test_cli_writes_the_travel_time_grid(
    write_i2: WriteI2, ocean: np.ndarray, tmp_path: Path
) -> None:
    out = tmp_path / "ttt.b"

    status = main([str(write_i2(ocean, x_min=-3.0)), "-E-1.6/0.0", f"-T{out}"])

    assert status == 0
    raw = out.read_bytes()
    assert struct.unpack_from("<3i", raw) == (30, 21, 0)
    hours = np.frombuffer(raw, dtype="<f4", offset=HEADER_SIZE).reshape(21, 30)
    assert hours[10, 14] == pytest.approx(0.0, abs=1e-12)
    assert hours[10, 15] > 0.0


def test_cli_reports_a_land_epicenter(
    write_i2: WriteI2,
    ocean: np.ndarray,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    depth = ocean.copy()
    depth[10, 4] = 3
    out = tmp_path / "ttt.b"

    status = main([str(write_i2(depth)), "-E0.4/0.0", f"-T{out}"])

    assert status == 1
    assert "land" in capsys.readouterr().err
    assert not out.exists()


def test_cli_rejects_a_malformed_epicenter(
    write_i2: WriteI2, ocean: np.ndarray, tmp_path: Path
) -> None:
    with pytest.raises(SystemExit):
        main([str(write_i2(ocean)), "-E0.4", f"-T{tmp_path / 'ttt.b'}"])


def test_cli_client_compatible_flag_starts_at_the_nearest_node(
    write_i2: WriteI2, ocean: np.ndarray, tmp_path: Path
) -> None:
    grid = write_i2(ocean, x_min=-3.0)
    default = tmp_path / "default.b"
    compatible = tmp_path / "compatible.b"

    main([str(grid), "-E-1.57/0.0", f"-T{default}"])
    main([str(grid), "-E-1.57/0.0", f"-T{compatible}", "--client-compatible"])

    default_hours = np.fromfile(default, dtype="<f4", offset=HEADER_SIZE)
    compatible_hours = np.fromfile(compatible, dtype="<f4", offset=HEADER_SIZE)
    start = 10 * 30 + 14
    assert compatible_hours[start] == 0.0
    assert default_hours[start] > 0.0
