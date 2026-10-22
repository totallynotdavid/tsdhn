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
_STEP_X = np.array([abs(i) for i, _ in CELLS[:_NEIGHBOURS]]) / _MAJOR
_STEP_Y = np.array([abs(j) for _, j in CELLS[:_NEIGHBOURS]]) / _MAJOR
_BIAS_ANGLE = 2.0 * math.pi / _NEIGHBOURS
_BIAS_FACTOR = np.float32(math.sqrt(math.sin(_BIAS_ANGLE) / _BIAS_ANGLE))


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


def _slowness(b: Bathymetry) -> np.ndarray:
    """Slowness in s/m, negative, on a grid padded with NaN; land is NaN."""
    g = _gravity(_latitudes(b, np.arange(b.ny)))[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        wet = b.depth < 0
        speed = np.sqrt((-b.depth).astype(np.float64) * g)
        inner = np.where(wet, -1.0 / speed, np.nan).astype(np.float32)
    padded = np.full((b.ny + 2 * _PAD, b.nx + 2 * _PAD), np.nan, dtype=np.float32)
    padded[_PAD:-_PAD, _PAD:-_PAD] = inner
    return padded


def _segment_lengths(b: Bathymetry) -> np.ndarray:
    """Metres per unit of mean slowness, per row and direction.

    A row's east-west scale uses the latitude of its own row for every segment
    that starts on it.
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


def _offsets(width: int) -> np.ndarray:
    return np.array([-j * width + i for i, j in CELLS], dtype=np.int64)


def locate_source(b: Bathymetry, lon: float, lat: float) -> tuple[int, int]:
    """Return (row, column) of the grid node nearest the epicenter."""
    if lat < b.y_min or lat > b.y_max:
        msg = f"epicenter latitude {lat:g} is outside the grid"
        raise ValueError(msg)
    while lon > b.x_min:
        lon -= 360.0
    while lon < b.x_min:
        lon += 360.0
    if lon > b.x_max:
        msg = f"epicenter longitude {lon:g} is outside the grid"
        raise ValueError(msg)
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
    source: int,
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
    key[source] = 0.0
    heap[0] = source
    pos[source] = 0
    size = 1
    counter = 1
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
        slowness[ij] = np.float32((1.0 / 3600.0) * np.float64(t))
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
            arrival = t - np.float32(length[row, k] * mean)
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
    lon1: float, lat1: float, lon2: np.ndarray, lat2: np.ndarray
) -> np.ndarray:
    a = _DEGREE * (90.0 - lat2)
    b = _DEGREE * (90.0 - lat1)
    c = _DEGREE * (lon2 - lon1)
    cos_c = np.cos(a) * math.cos(b) + np.sin(a) * math.sin(b) * np.cos(c)
    angle = np.arccos(np.clip(cos_c, -1.0, 1.0))
    same = (lat2 == lat1) & (lon2 == lon1)
    return np.where(same, 0.0, angle / _DEGREE)


def _source_slope(b: Bathymetry, hours: np.ndarray, row: int, column: int) -> float:
    """Mean time gained per km within a quarter degree of the source."""
    radius = min(0.25, 2.0 * b.x_inc)
    lat0 = float(_latitudes(b, np.array([row]))[0])
    lon0 = float(_longitudes(b, np.array([column]))[0])
    reach_x = math.ceil(radius / (b.x_inc * math.cos(lat0 * _DEGREE)))
    reach_y = math.ceil(radius / b.y_inc)
    columns = np.arange(max(0, column - reach_x), min(b.nx - 1, column + reach_x) + 1)
    rows = np.arange(max(0, row - reach_y), min(b.ny - 1, row + reach_y) + 1)
    distance = _great_circle_degrees(
        lon0,
        lat0,
        _longitudes(b, columns)[None, :],
        _latitudes(b, rows)[:, None],
    )
    window = hours[np.ix_(rows, columns)].astype(np.float64)
    near = (distance <= radius) & ~np.isnan(window)
    total = float(distance[near].sum())
    if total <= 0.0:
        return 0.0
    gained = float(np.abs(window[near] - float(hours[row, column])).sum())
    return 3600.0 * (gained / total) * (180.0 / math.pi / (0.001 * EARTH_RADIUS_M))


def travel_times(b: Bathymetry, lon: float, lat: float) -> TravelTimes:
    """Propagate a tsunami from an epicenter over open water.

    Raises ValueError when the epicenter is outside the grid or on land, and
    for grids that span 360 degrees of longitude.
    """
    if abs(b.x_max - b.x_min - 360.0) < 1.0e-8:
        msg = "grids spanning 360 degrees of longitude are not supported"
        raise ValueError(msg)
    row, column = locate_source(b, lon, lat)
    depth = b.depth[row, column]
    if np.isnan(depth) or depth >= 0:
        msg = f"epicenter {lon:g}/{lat:g} lies on land"
        raise ValueError(msg)
    slowness = _slowness(b)
    width = b.nx + 2 * _PAD
    key = np.where(np.isnan(slowness), _BLOCKED, _UNREACHED).ravel()
    water = int(np.count_nonzero(key == _UNREACHED))
    work = slowness.ravel()
    settled = _propagate(
        work,
        key,
        (row + _PAD) * width + column + _PAD,
        width,
        _offsets(width),
        _WEIGHT_START,
        _WEIGHT_CELL,
        _WEIGHT_VALUE,
        _BLOCK_START,
        _BLOCK_CELL,
        _segment_lengths(b),
    )
    inner = slowness[_PAD:-_PAD, _PAD:-_PAD]
    with np.errstate(invalid="ignore"):
        hours = np.where(inner < 0, np.nan, inner * _BIAS_FACTOR).astype(np.float32)
    return TravelTimes(
        hours=hours,
        source_slope_s_per_km=_source_slope(b, hours, row, column),
        unreached=water - settled,
    )
