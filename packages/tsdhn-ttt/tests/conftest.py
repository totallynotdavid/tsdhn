import struct
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from tsdhn_ttt.grid import HEADER_SIZE, Bathymetry

type WriteI2 = Callable[..., Path]


def write_depth_grid(path: Path, bathymetry: Bathymetry) -> None:
    """Write a bathymetry as a GMT native 16-bit grid; NaN becomes -32768."""
    depth = bathymetry.depth
    raw = np.where(np.isnan(depth), -32768, depth).astype("<i2")
    header = struct.pack(
        "<3i10d",
        bathymetry.nx,
        bathymetry.ny,
        bathymetry.node_offset,
        bathymetry.x_min,
        bathymetry.x_max,
        bathymetry.y_min,
        bathymetry.y_max,
        float(np.nanmin(depth)),
        float(np.nanmax(depth)),
        bathymetry.x_inc,
        bathymetry.y_inc,
        1.0,
        0.0,
    )
    path.write_bytes(header.ljust(HEADER_SIZE, b"\0") + raw.tobytes())


@pytest.fixture
def write_i2(tmp_path: Path) -> WriteI2:
    """Write a depth array as a GMT native 16-bit grid and return its path."""

    def write(
        depth: np.ndarray,
        *,
        x_min: float = 0.0,
        y_max: float = 1.0,
        step: float = 0.1,
        node_offset: int = 0,
        name: str = "depth.i2",
    ) -> Path:
        ny, nx = depth.shape
        span = 1 - node_offset
        bathymetry = Bathymetry(
            x_min=x_min,
            x_max=x_min + (nx - span) * step,
            y_min=y_max - (ny - span) * step,
            y_max=y_max,
            node_offset=node_offset,
            depth=depth.astype(np.float32),
        )
        path = tmp_path / name
        write_depth_grid(path, bathymetry)
        return path

    return write


@pytest.fixture
def ocean() -> np.ndarray:
    """A 4 km deep ocean, 21 rows by 30 columns."""
    return np.full((21, 30), -4000, dtype=np.int16)
