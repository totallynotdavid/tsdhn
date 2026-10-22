"""Read bathymetry from a GMT native short grid and write a float travel-time grid."""

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_INT_FIELDS = 3
_DOUBLE_FIELDS = 10
_FIXED = struct.Struct(f"<{_INT_FIELDS}i{_DOUBLE_FIELDS}d")
# x units, y units, z units, title, command, remark.
_TEXT_WIDTHS = (80, 80, 80, 80, 320, 160)
HEADER_SIZE = _FIXED.size + sum(_TEXT_WIDTHS)
_SHORT_NAN = (-32768, 32767)


@dataclass(frozen=True)
class Bathymetry:
    """Depths in metres, negative below sea level; NaN marks land and no data.

    `depth` is row-major with the northern row first, as in the file.
    """

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    node_offset: int
    depth: np.ndarray

    @property
    def ny(self) -> int:
        return int(self.depth.shape[0])

    @property
    def nx(self) -> int:
        return int(self.depth.shape[1])

    @property
    def x_inc(self) -> float:
        return (self.x_max - self.x_min) / (self.nx - (1 - self.node_offset))

    @property
    def y_inc(self) -> float:
        return (self.y_max - self.y_min) / (self.ny - (1 - self.node_offset))


def read_bathymetry(path: Path) -> Bathymetry:
    """Read a GMT native 16-bit grid (`=bs`). Header scaling is ignored."""
    with path.open("rb") as handle:
        header = handle.read(HEADER_SIZE)
        if len(header) < HEADER_SIZE:
            msg = f"{path}: file is shorter than a GMT grid header"
            raise ValueError(msg)
        nx, ny, node_offset, x_min, x_max, y_min, y_max, *_ = _FIXED.unpack_from(header)
        raw = np.fromfile(handle, dtype="<i2", count=nx * ny)
    if raw.size != nx * ny:
        msg = f"{path}: expected {nx * ny} values, found {raw.size}"
        raise ValueError(msg)
    depth = raw.reshape(ny, nx).astype(np.float32)
    depth[np.isin(raw.reshape(ny, nx), _SHORT_NAN)] = np.nan
    return Bathymetry(x_min, x_max, y_min, y_max, node_offset, depth)


def write_travel_times(
    path: Path,
    bathymetry: Bathymetry,
    hours: np.ndarray,
    epicenter: tuple[float, float],
    slope_s_per_km: float,
) -> None:
    """Write travel times in hours as a GMT native float grid (`=bf`)."""
    water = hours[~np.isnan(hours)]
    z_min = float(water.min()) if water.size else float(np.finfo(np.float32).max)
    z_max = float(water.max()) if water.size else -float(np.finfo(np.float32).max)
    lon, lat = epicenter
    remark = (
        f"{lon:g} {lat:g} 0 0 0 0 0 0 {slope_s_per_km:g} "
        "[x, y, M, D, Y, hh, mm, ss, rate (s/km)]"
    )
    texts = (
        "longitude [degrees_east]",
        "latitude [degrees_north]",
        "hour",
        "Tsunami travel times",
        "Grid was saved by tsdhn_ttt",
        remark,
    )
    fixed = _FIXED.pack(
        bathymetry.nx,
        bathymetry.ny,
        bathymetry.node_offset,
        bathymetry.x_min,
        bathymetry.x_max,
        bathymetry.y_min,
        bathymetry.y_max,
        z_min,
        z_max,
        bathymetry.x_inc,
        bathymetry.y_inc,
        1.0,
        0.0,
    )
    text_block = b"".join(
        text.encode("ascii").ljust(width, b"\0")
        for text, width in zip(texts, _TEXT_WIDTHS, strict=True)
    )
    with path.open("wb") as handle:
        handle.write(fixed)
        handle.write(text_block)
        handle.write(np.ascontiguousarray(hours, dtype="<f4").tobytes())
