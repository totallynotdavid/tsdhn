"""Tsunami travel times over a bathymetry grid.

The wavefront advances by Dijkstra's algorithm on the grid, where each node
reaches 120 neighbours out to 13 cells away. A neighbour's cost is the length of
the straight segment times the mean slowness (1 / sqrt(g * depth)) along it.
Straight segments between grid nodes follow the 120 directions only, so paths run
slightly longer than the true ones; a final factor, sqrt(sin(f) / f) with
f = 2 pi / 120, removes that bias on average.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import numba
import numpy as np

from tsdhn_ttt._stencil import BLOCKERS, CELLS, WEIGHTS
from tsdhn_ttt.grid import Bathymetry

EARTH_RADIUS_M = 6371007.181
_DEGREE = math.pi / 180.0
_M_PER_DEGREE = 2.0 * math.pi * EARTH_RADIUS_M / 360.0
_PAD = 13
_NEIGHBOURS = 120
_SEED_CELLS = 4.0
_UNREACHED = np.float32(1.0e33)
_SETTLED = np.float32(1.0e34)
_BLOCKED = np.float32(1.0e35)


def _jit[F: Callable[..., Any]](fn: F) -> F:
    return cast("F", numba.njit(cache=True)(fn))


@dataclass(frozen=True)
class TravelTimes:
    """Result of one propagation."""

    hours: np.ndarray
    source_slope_s_per_km: float
    unreached: int

    @property
    def maximum_hours(self) -> float:
        return float(np.nanmax(self.hours))


def _csr(rows: list[list[int]]) -> tuple[np.ndarray, np.ndarray]:
    start = np.cumsum([0, *(len(row) for row in rows)]).astype(np.int64)
    flat = np.array([cell for row in rows for cell in row], dtype=np.int64)
    return start, flat


_WEIGHT_START, _WEIGHT_CELL = _csr([[cell for cell, _ in row] for row in WEIGHTS])
_WEIGHT_VALUE = np.array([w for row in WEIGHTS for _, w in row], dtype=np.float64)
_BLOCK_START, _BLOCK_CELL = _csr(
    [
        sorted({cell for cell, _ in row} | {c for k, c in BLOCKERS if k == k_row})
        for k_row, row in enumerate(WEIGHTS)
    ]
)
_MAJOR = np.array([max(abs(i), abs(j)) for i, j in CELLS[:_NEIGHBOURS]], dtype=float)
_STEP_LON = np.array([i for i, _ in CELLS[:_NEIGHBOURS]], dtype=float)
_STEP_LAT = np.array([j for _, j in CELLS[:_NEIGHBOURS]], dtype=float)
_STEP_X = np.array([abs(i) for i, _ in CELLS[:_NEIGHBOURS]]) / _MAJOR
_STEP_Y = np.array([abs(j) for _, j in CELLS[:_NEIGHBOURS]]) / _MAJOR
_BIAS_ANGLE = 2.0 * math.pi / _NEIGHBOURS
_BIAS_FACTOR = math.sqrt(math.sin(_BIAS_ANGLE) / _BIAS_ANGLE)


def _longitudes(b: Bathymetry, columns: np.ndarray) -> np.ndarray:
    offset = 0.5 * b.node_offset
    lon = b.x_min + (columns + offset) * b.x_inc
    return np.where(columns == b.nx - 1, b.x_max - offset * b.x_inc, lon)


def _latitudes(b: Bathymetry, rows: np.ndarray) -> np.ndarray:
    offset = 0.5 * b.node_offset
    lat = b.y_max - (rows + offset) * b.y_inc
    return np.where(rows == b.ny - 1, b.y_min + offset * b.y_inc, lat)


def _gravity(lat: np.ndarray) -> np.ndarray:
    s = np.sin(lat * _DEGREE)
    s *= s
    return 9.7803267715 * (1.0 + 0.0052790414 * s + 0.0000232718 * s * s)


def _slowness(b: Bathymetry, dtype: type[np.floating]) -> np.ndarray:
    """Slowness in s/m, negative, on a grid padded with NaN; land is NaN."""
    g = _gravity(_latitudes(b, np.arange(b.ny)))[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        wet = b.depth < 0
        speed = np.sqrt((-b.depth).astype(np.float64) * g)
        inner = np.where(wet, -1.0 / speed, np.nan).astype(dtype)
    padded = np.full((b.ny + 2 * _PAD, b.nx + 2 * _PAD), np.nan, dtype=dtype)
    padded[_PAD:-_PAD, _PAD:-_PAD] = inner
    return padded


def _client_lengths(b: Bathymetry) -> np.ndarray:
    """Use each segment's start-row latitude, as `ttt_client` does.

    The latitude is the grid edge, even when the grid is pixel-registered.
    """
    half_x = (
        0.5
        * b.x_inc
        * _M_PER_DEGREE
        * np.cos(_DEGREE * (b.y_max - np.arange(b.ny) * b.y_inc))
    )
    half_y = 0.5 * b.y_inc * _M_PER_DEGREE
    lengths: np.ndarray = np.hypot(
        _STEP_X[None, :] * half_x[:, None], _STEP_Y[None, :] * half_y
    )
    return lengths


def _sphere_lengths(b: Bathymetry) -> np.ndarray:
    """Metres per unit of mean slowness, per row and direction, on the sphere.

    Each is the great-circle length between the segment's end nodes, at their
    real latitudes, shared out over the cell steps of the segment's major axis.
    """
    lat_start = _latitudes(b, np.arange(b.ny))[:, None]
    lat_end = lat_start + _STEP_LAT[None, :] * b.y_inc
    angle = _great_circle_degrees(
        lat_start, np.zeros_like(lat_start), lat_end, _STEP_LON[None, :] * b.x_inc
    )
    lengths: np.ndarray = _M_PER_DEGREE * angle / (2.0 * _MAJOR[None, :])
    return lengths


def _offsets(width: int) -> np.ndarray:
    return np.array([-j * width + i for i, j in CELLS], dtype=np.int64)


def locate_source(b: Bathymetry, lon: float, lat: float) -> tuple[int, int]:
    """Return (row, column) of the grid node nearest the epicenter."""
    lon = _check_epicenter(b, lon, lat)
    offset = 0.5 * b.node_offset
    column = round((lon - b.x_min) / b.x_inc - offset)
    row = b.ny - 1 - round((lat - b.y_min) / b.y_inc - offset)
    return row, column


@_jit
def _less(key: np.ndarray, seq: np.ndarray, a: int, b: int) -> bool:
    return bool(key[a] < key[b] or (key[a] == key[b] and seq[a] < seq[b]))


@_jit
def _sift_up(
    heap: np.ndarray, pos: np.ndarray, key: np.ndarray, seq: np.ndarray, i: int
) -> None:
    node = heap[i]
    while i > 0:
        parent = (i - 1) // 2
        above = heap[parent]
        if not _less(key, seq, node, above):
            break
        heap[i] = above
        pos[above] = i
        i = parent
    heap[i] = node
    pos[node] = i


@_jit
def _sift_down(
    heap: np.ndarray,
    pos: np.ndarray,
    key: np.ndarray,
    seq: np.ndarray,
    size: int,
    i: int,
) -> None:
    node = heap[i]
    while True:
        child = 2 * i + 1
        if child >= size:
            break
        if child + 1 < size and _less(key, seq, heap[child + 1], heap[child]):
            child += 1
        if not _less(key, seq, heap[child], node):
            break
        heap[i] = heap[child]
        pos[heap[i]] = i
        i = child
    heap[i] = node
    pos[node] = i


@_jit
def _propagate(
    slowness: np.ndarray,
    key: np.ndarray,
    seed: np.ndarray,
    seed_time: np.ndarray,
    width: int,
    offsets: np.ndarray,
    weight_start: np.ndarray,
    weight_cell: np.ndarray,
    weight_value: np.ndarray,
    block_start: np.ndarray,
    block_cell: np.ndarray,
    length: np.ndarray,
) -> int:
    """Settle nodes in order of arrival; return how many were settled.

    `slowness` holds negative slowness on open water and NaN elsewhere. A node
    that is settled has its cell overwritten with its travel time in hours, and
    from then on blocks any longer segment that crosses it. `key` holds each
    node's tentative time while queued. Nodes with equal times leave the queue
    in the order they were queued.
    """
    heap = np.empty(key.size, dtype=np.int32)
    pos = np.full(key.size, -1, dtype=np.int32)
    seq = np.zeros(key.size, dtype=np.int64)
    patch = offsets.size
    open_cell = np.empty(patch, dtype=np.bool_)
    value = np.empty(patch, dtype=np.float64)
    cost = np.empty(1, dtype=key.dtype)
    size = 0
    counter = 1
    for s in range(seed.size):
        key[seed[s]] = seed_time[s]
        seq[seed[s]] = counter
        counter += 1
        heap[size] = seed[s]
        size += 1
        _sift_up(heap, pos, key, seq, size - 1)
    settled = 0
    while size > 0:
        ij = heap[0]
        t = key[ij]
        size -= 1
        pos[ij] = -1
        if size > 0:
            heap[0] = heap[size]
            pos[heap[0]] = 0
            _sift_down(heap, pos, key, seq, size, 0)
        key[ij] = _SETTLED
        settled += 1
        row = ij // width - _PAD
        closed = 0
        for c in range(patch):
            v = slowness[ij + offsets[c]]
            value[c] = v
            open_cell[c] = v < 0
            if not open_cell[c]:
                closed += 1
        own = np.float64(slowness[ij])
        slowness[ij] = (1.0 / 3600.0) * np.float64(t)
        for k in range(_NEIGHBOURS):
            kk = ij + offsets[k]
            if key[kk] > _UNREACHED:
                continue
            if closed > 0:
                free = True
                for q in range(block_start[k], block_start[k + 1]):
                    if not open_cell[block_cell[q]]:
                        free = False
                        break
                if not free:
                    continue
            mean = own
            for q in range(weight_start[k], weight_start[k + 1]):
                mean += weight_value[q] * value[weight_cell[q]]
            cost[0] = length[row, k] * mean
            arrival = t - cost[0]
            if key[kk] == _UNREACHED:
                key[kk] = arrival
                seq[kk] = counter
                counter += 1
                heap[size] = kk
                size += 1
                _sift_up(heap, pos, key, seq, size - 1)
            elif arrival < key[kk]:
                key[kk] = arrival
                seq[kk] = counter
                counter += 1
                _sift_up(heap, pos, key, seq, pos[kk])
    return settled


def _great_circle_degrees(
    lat1: np.ndarray | float,
    lon1: np.ndarray | float,
    lat2: np.ndarray | float,
    lon2: np.ndarray | float,
) -> np.ndarray:
    """Angle in degrees between two points, by the haversine formula."""
    half_lat = np.sin(0.5 * _DEGREE * (lat2 - lat1))
    half_lon = np.sin(0.5 * _DEGREE * (lon2 - lon1))
    h = half_lat**2 + np.cos(_DEGREE * lat1) * np.cos(_DEGREE * lat2) * half_lon**2
    angle: np.ndarray = 2.0 * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0))) / _DEGREE
    return angle


def _source_slope(
    b: Bathymetry, hours: np.ndarray, row: int, column: int, lon0: float, lat0: float
) -> float:
    """Mean time gained per km around (lon0, lat0).

    Time is counted from zero at that point. `row` and `column` select the
    surrounding window.
    """
    radius = min(0.25, 2.0 * b.x_inc)
    reach_x = math.ceil(radius / (b.x_inc * math.cos(lat0 * _DEGREE)))
    reach_y = math.ceil(radius / b.y_inc)
    columns = np.arange(max(0, column - reach_x), min(b.nx - 1, column + reach_x) + 1)
    rows = np.arange(max(0, row - reach_y), min(b.ny - 1, row + reach_y) + 1)
    distance = _great_circle_degrees(
        lat0,
        lon0,
        _latitudes(b, rows)[:, None],
        _longitudes(b, columns)[None, :],
    )
    window = hours[np.ix_(rows, columns)].astype(np.float64)
    near = (distance <= radius) & ~np.isnan(window)
    total = float(distance[near].sum())
    if total <= 0.0:
        return 0.0
    gained = float(np.abs(window[near]).sum())
    return 3600.0 * (gained / total) * (180.0 / math.pi / (0.001 * EARTH_RADIUS_M))


@dataclass(frozen=True)
class _Seeds:
    """Nodes where the wavefront starts, their times in seconds, and its centre."""

    index: np.ndarray
    seconds: np.ndarray
    lon: float
    lat: float


_Seeder = Callable[[Bathymetry, np.ndarray, float, float], _Seeds]


def _seed_nearest_node(
    b: Bathymetry, slowness: np.ndarray, lon: float, lat: float
) -> _Seeds:
    """Start the wavefront at the node nearest the epicenter, at time zero."""
    row, column = locate_source(b, lon, lat)
    return _Seeds(
        np.array([(row + _PAD) * (b.nx + 2 * _PAD) + column + _PAD], dtype=np.int64),
        np.zeros(1),
        float(_longitudes(b, np.array([column]))[0]),
        float(_latitudes(b, np.array([row]))[0]),
    )


def _seed_around_epicenter(
    b: Bathymetry, slowness: np.ndarray, lon: float, lat: float
) -> _Seeds:
    """Start the wavefront at the water nodes around the epicenter.

    A seed is within `_SEED_CELLS` cells and has an unobstructed segment from
    the epicenter. Its time is the segment length times mean slowness.
    """
    lon = _wrap_longitude(b, lon)
    offset = 0.5 * b.node_offset
    x = (lon - b.x_min) / b.x_inc - offset
    y = (lat - b.y_min) / b.y_inc - offset
    cell_m = b.y_inc * _M_PER_DEGREE
    reach_x = _SEED_CELLS * b.y_inc / (b.x_inc * math.cos(lat * _DEGREE))
    columns = np.arange(
        max(0, math.ceil(x - reach_x)), min(b.nx - 1, math.floor(x + reach_x)) + 1
    )
    south = np.arange(
        max(0, math.ceil(y - _SEED_CELLS)),
        min(b.ny - 1, math.floor(y + _SEED_CELLS)) + 1,
    )
    rows = b.ny - 1 - south
    angle = _great_circle_degrees(
        lat, lon, _latitudes(b, rows)[:, None], _longitudes(b, columns)[None, :]
    )
    inner = slowness[_PAD:-_PAD, _PAD:-_PAD]
    width = b.nx + 2 * _PAD
    index = []
    seconds = []
    for i, row in enumerate(rows):
        for j, column in enumerate(columns):
            metres = float(angle[i, j]) * _M_PER_DEGREE
            if metres > _SEED_CELLS * cell_m or not inner[row, column] < 0:
                continue
            mean = _mean_slowness(
                inner, x, y, float(column), float(south[i]), metres / cell_m
            )
            if mean is None:
                continue
            index.append((row + _PAD) * width + column + _PAD)
            seconds.append(-metres * mean)
    return _Seeds(
        np.array(index, dtype=np.int64), np.array(seconds, dtype=np.float64), lon, lat
    )


def _mean_slowness(
    inner: np.ndarray, x0: float, y0: float, x1: float, y1: float, cells: float
) -> float | None:
    """Mean slowness along a straight segment, or None when it meets land.

    Points are (column, rows counted from the south). The trapezoid rule over
    slowness interpolated linearly between nodes agrees with the kernel's
    weights to second order in the cell size.
    """
    ny, nx = inner.shape
    steps = max(2, math.ceil(2.0 * cells))
    along = np.arange(steps + 1) / steps
    px = x0 + along * (x1 - x0)
    py = y0 + along * (y1 - y0)
    nearest = inner[
        ny - 1 - np.clip(np.rint(py), 0, ny - 1).astype(int),
        np.clip(np.rint(px), 0, nx - 1).astype(int),
    ]
    if not (nearest < 0).all():
        return None
    column = np.clip(np.floor(px), 0, nx - 2).astype(int)
    south = np.clip(np.floor(py), 0, ny - 2).astype(int)
    fx = np.clip(px - column, 0.0, 1.0)
    fy = np.clip(py - south, 0.0, 1.0)
    corners = [
        inner[ny - 1 - south - dy, column + dx].astype(np.float64)
        for dy in (0, 1)
        for dx in (0, 1)
    ]
    interpolated = np.where(
        np.isnan(corners[0] + corners[1] + corners[2] + corners[3]),
        nearest,
        corners[0] * (1 - fx) * (1 - fy)
        + corners[1] * fx * (1 - fy)
        + corners[2] * (1 - fx) * fy
        + corners[3] * fx * fy,
    )
    return float(
        (interpolated.sum() - 0.5 * (interpolated[0] + interpolated[-1])) / steps
    )


def _wrap_longitude(b: Bathymetry, lon: float) -> float:
    while lon > b.x_min:
        lon -= 360.0
    while lon < b.x_min:
        lon += 360.0
    return lon


def _check_epicenter(b: Bathymetry, lon: float, lat: float) -> float:
    """Return the longitude within the grid's range, or raise ValueError."""
    if lat < b.y_min or lat > b.y_max:
        msg = f"epicenter latitude {lat:g} is outside the grid"
        raise ValueError(msg)
    wrapped = _wrap_longitude(b, lon)
    if wrapped > b.x_max:
        msg = f"epicenter longitude {wrapped:g} is outside the grid"
        raise ValueError(msg)
    return wrapped


def _solve(
    b: Bathymetry,
    lon: float,
    lat: float,
    *,
    dtype: type[np.floating],
    lengths: np.ndarray,
    seeder: _Seeder,
) -> TravelTimes:
    """Propagate in the given arithmetic, with the given segment lengths.

    `lengths` is a table from `_client_lengths` or `_sphere_lengths`. `seeder`
    chooses where the wavefront starts.
    """
    row, column = locate_source(b, lon, lat)
    depth = b.depth[row, column]
    if np.isnan(depth) or depth >= 0:
        msg = f"epicenter {lon:g}/{lat:g} lies on land"
        raise ValueError(msg)
    slowness = _slowness(b, dtype)
    width = b.nx + 2 * _PAD
    key = np.where(np.isnan(slowness), _BLOCKED, _UNREACHED).astype(dtype).ravel()
    water = int(np.count_nonzero(key == _UNREACHED))
    work = slowness.ravel()
    seeds = seeder(b, slowness, lon, lat)
    settled = _propagate(
        work,
        key,
        seeds.index,
        seeds.seconds,
        width,
        _offsets(width),
        _WEIGHT_START,
        _WEIGHT_CELL,
        _WEIGHT_VALUE,
        _BLOCK_START,
        _BLOCK_CELL,
        lengths,
    )
    inner = slowness[_PAD:-_PAD, _PAD:-_PAD]
    with np.errstate(invalid="ignore"):
        hours = np.where(inner < 0, np.nan, inner * dtype(_BIAS_FACTOR)).astype(dtype)
    return TravelTimes(
        hours=hours,
        source_slope_s_per_km=_source_slope(
            b, hours, row, column, seeds.lon, seeds.lat
        ),
        unreached=water - settled,
    )


def travel_times(
    b: Bathymetry, lon: float, lat: float, *, client_compatible: bool = False
) -> TravelTimes:
    """Propagate a tsunami from an epicenter over open water.

    The default is the most accurate method: float64, segments measured on the
    sphere, and the wavefront started at the epicenter. `client_compatible`
    reproduces `ttt_client` instead: float32, a segment measured with the
    cosine of its start row, and the wavefront started at the nearest node.

    Raises ValueError when the epicenter is outside the grid or on land, and
    for grids that span 360 degrees of longitude.
    """
    if abs(b.x_max - b.x_min - 360.0) < 1.0e-8:
        msg = "grids spanning 360 degrees of longitude are not supported"
        raise ValueError(msg)
    if client_compatible:
        return _solve(
            b,
            lon,
            lat,
            dtype=np.float32,
            lengths=_client_lengths(b),
            seeder=_seed_nearest_node,
        )
    return _solve(
        b,
        lon,
        lat,
        dtype=np.float64,
        lengths=_sphere_lengths(b),
        seeder=_seed_around_epicenter,
    )
