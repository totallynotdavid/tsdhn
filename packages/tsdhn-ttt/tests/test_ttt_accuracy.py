"""Check the default solver against closed-form travel times.

The grids use the solver's gravity and exact speed laws, so the exact time to
every node is known. The solver's time lies between two bounds derived from the
method. Distances are in cells and measured in the local metric, where a cell is
`cos(lat)` wide and 1 high. A node T lies D cells from the source.

Lower bound. A path of stencil segments is never shorter than the geodesic, and
the solver multiplies the path by FACTOR, so time >= FACTOR * exact.

Upper bound, FACTOR * exact * (1 / cos(g / 2) + (K + E) / D). Each term is the
cost of one thing the stencil cannot do:

- g is the largest angle between two neighbouring stencil directions. A target
  between directions v1 and v2 at angle g is reached by real multiples of v1 and
  v2 at most D / cos(g / 2) cells long, the worst case being the bisector.
- K is the lattice term. The multiples must be whole numbers. Write the target
  as a * v1 + b * v2 and keep the whole parts of a and b. What is left is a node
  r inside the parallelogram of v1 and v2, whose cost exceeds its real
  combination by at most K, the largest such excess over all pairs and nodes r,
  found by a shortest-path search over the stencil. K does not grow with D, so
  it adds K / D.
- E is the start term. An epicenter between nodes starts the wavefront at the
  nodes within 4 cells, each timed by the straight segment from the epicenter.
  The best of them for a bearing costs d * (1 - cos(alpha)) cells more than the
  straight line, d being its distance and alpha its angle from the bearing. E
  is the largest over all bearings. It is zero when the epicenter is a node.

Every path stays inside the grid, so g and K are those of the cell shape at the
poleward edge, where cells are narrowest. Both grow as `cos(lat)` falls.

Evaluation error. A segment is the great-circle chord between its end nodes,
but the slowness is sampled along the straight line in longitude and latitude.
On a parallel the chord is shorter by about (dx sin(lat))^2 / 24, dx being the
segment's longitude span, at most 13 cells. A segment also integrates a
slowness that bends with latitude by the trapezoid rule, which overestimates by
(h^2 / 12) * f'' / f for a sample spacing h of one cell. Depths are float32,
which moves the speed by at most 2^-25. These add to both bounds.
"""

import heapq
import math
from dataclasses import dataclass, replace
from functools import cache

import numpy as np
import pytest

from tsdhn_ttt import Bathymetry, travel_times
from tsdhn_ttt._stencil import CELLS
from tsdhn_ttt.solver import EARTH_RADIUS_M

STEP = 1.0 / 15.0
CELL_RAD = math.radians(STEP)
CELL_M = EARTH_RADIUS_M * CELL_RAD
FACTOR = math.sqrt(math.sin(2 * math.pi / 120) / (2 * math.pi / 120))
STENCIL = CELLS[:120]
LONGEST_STEP = max(max(abs(i), abs(j)) for i, j in STENCIL)
SEED_CELLS = 4.0
DEPTH_ROUNDING = 2.0**-25
SPEED = 200.0


def _gravity(lat: np.ndarray) -> np.ndarray:
    s2 = np.sin(np.radians(lat)) ** 2
    return np.asarray(9.7803267715 * (1.0 + 0.0052790414 * s2 + 0.0000232718 * s2 * s2))


def _angle(lat0: float, lon0: float, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Great-circle angle in radians, by the haversine formula."""
    a = np.sin(np.radians(lat - lat0) / 2) ** 2
    a = a + math.cos(math.radians(lat0)) * np.cos(np.radians(lat)) * (
        np.sin(np.radians(lon - lon0) / 2) ** 2
    )
    return np.asarray(2.0 * np.arcsin(np.sqrt(a)))


@cache
def _stencil_terms(cos_lat: float) -> tuple[float, float]:
    """Return the largest gap in radians and the lattice term K in cells."""
    length = {s: math.hypot(s[0] * cos_lat, s[1]) for s in STENCIL}
    bearing = sorted((math.atan2(j, i * cos_lat), (i, j)) for i, j in STENCIL)
    neighbours = [
        (bearing[k][1], bearing[(k + 1) % len(bearing)][1]) for k in range(len(bearing))
    ]
    gap = max(
        (bearing[(k + 1) % len(bearing)][0] - bearing[k][0]) % (2 * math.pi)
        for k in range(len(bearing))
    )
    # Shortest stencil path to every node of a window; a path that would leave
    # the window is ignored, which only raises K.
    reach = 3 * LONGEST_STEP
    cost = {(0, 0): 0.0}
    queue = [(0.0, (0, 0))]
    while queue:
        spent, node = heapq.heappop(queue)
        if spent > cost[node]:
            continue
        for step in STENCIL:
            end = (node[0] + step[0], node[1] + step[1])
            if abs(end[0]) > reach or abs(end[1]) > reach:
                continue
            if spent + length[step] < cost.get(end, math.inf):
                cost[end] = spent + length[step]
                heapq.heappush(queue, (cost[end], end))
    lattice = 0.0
    for v1, v2 in neighbours:
        det = v1[0] * v2[1] - v1[1] * v2[0]
        xs = (0, v1[0], v2[0], v1[0] + v2[0])
        ys = (0, v1[1], v2[1], v1[1] + v2[1])
        for x in range(min(xs), max(xs) + 1):
            for y in range(min(ys), max(ys) + 1):
                a = (x * v2[1] - y * v2[0]) / det
                b = (v1[0] * y - v1[1] * x) / det
                if 0 <= a < 1 and 0 <= b < 1:
                    real = a * length[v1] + b * length[v2]
                    lattice = max(lattice, cost[(x, y)] - real)
    return gap, lattice


def _start_term(east: float, north: float, cos_lat: float) -> float:
    """Return E in cells for an epicenter `east`, `north` cells from a node."""
    span = math.ceil(SEED_CELLS / cos_lat) + 1
    nodes = np.array(
        [
            ((i - east) * cos_lat, j - north)
            for i in range(-span, span + 1)
            for j in range(-span, span + 1)
        ]
    )
    distance = np.hypot(nodes[:, 0], nodes[:, 1])
    nodes, distance = nodes[distance <= SEED_CELLS], distance[distance <= SEED_CELLS]
    theta = np.linspace(0.0, 2 * np.pi, 7200, endpoint=False)
    along = nodes[:, 0, None] * np.cos(theta) + nodes[:, 1, None] * np.sin(theta)
    return float((distance[:, None] - along).min(axis=0).max())


@dataclass(frozen=True)
class Case:
    """A speed law and the exact travel time it implies from (lon0, lat0)."""

    lat: float
    half_lon: float
    half_lat: float

    @property
    def cos_lat(self) -> float:
        """Cosine of the latitude farthest from the equator in the grid."""
        return math.cos(math.radians(abs(self.lat) + self.half_lat))

    @property
    def evaluation_error(self) -> float:
        return DEPTH_ROUNDING

    def speed(self, lat: np.ndarray) -> np.ndarray:
        return np.full_like(lat, SPEED)

    def seconds(
        self, lon0: float, lat0: float, lat: np.ndarray, lon: np.ndarray
    ) -> np.ndarray:
        return EARTH_RADIUS_M * _angle(lat0, lon0, lat, lon) / SPEED


@dataclass(frozen=True)
class MercatorCase(Case):
    """Speed a * cos(lat): travel time is flat distance in Mercator coordinates.

    With slowness 1 / (a cos(lat)) the metric is that of the plane in
    (longitude, Mercator y), so the exact time is R / a times the plane distance.
    Rays are straight there, so oblique directions have an exact answer.
    """

    @property
    def evaluation_error(self) -> float:
        tan2 = math.tan(math.acos(self.cos_lat)) ** 2
        chord = (1.0 - self.cos_lat**2) * (LONGEST_STEP * CELL_RAD) ** 2 / 24.0
        trapezoid = CELL_RAD**2 / 12.0 * (1.0 + 2.0 * tan2)
        return DEPTH_ROUNDING + chord + trapezoid

    def speed(self, lat: np.ndarray) -> np.ndarray:
        return SPEED * np.cos(np.radians(lat)) / math.cos(math.radians(self.lat))

    def seconds(
        self, lon0: float, lat0: float, lat: np.ndarray, lon: np.ndarray
    ) -> np.ndarray:
        a = SPEED / math.cos(math.radians(self.lat))
        y = np.arctanh(np.sin(np.radians(lat))) - math.atanh(
            math.sin(math.radians(lat0))
        )
        return EARTH_RADIUS_M * np.hypot(y, np.radians(lon - lon0)) / a


CASES = {
    "equator": Case(0.0, 5.0, 5.0),
    "60 degrees": Case(60.0, 10.0, 5.0),
    "speed changes with latitude": MercatorCase(40.0, 7.0, 5.0),
}


@dataclass(frozen=True)
class Scene:
    bathymetry: Bathymetry
    lon: np.ndarray
    lat: np.ndarray
    lon0: float
    lat0: float

    def metres_from(self, lon0: float, lat0: float) -> np.ndarray:
        return EARTH_RADIUS_M * _angle(lat0, lon0, self.lat, self.lon)


def _scene(case: Case, node_offset: int) -> Scene:
    span = 1 - node_offset
    nx = round(2 * case.half_lon / STEP) + span
    ny = round(2 * case.half_lat / STEP) + span
    shape = Bathymetry(
        -case.half_lon,
        case.half_lon,
        case.lat - case.half_lat,
        case.lat + case.half_lat,
        node_offset,
        np.zeros((ny, nx), dtype=np.float32),
    )
    rows = np.arange(ny)[:, None]
    columns = np.arange(nx)[None, :]
    lat = shape.y_max - (rows + 0.5 * node_offset) * shape.y_inc + 0 * columns
    lon = shape.x_min + (columns + 0.5 * node_offset) * shape.x_inc + 0 * rows
    depth = (case.speed(lat) ** 2 / _gravity(lat)).astype(np.float32)
    return Scene(
        replace(shape, depth=-depth),
        lon,
        lat,
        float(lon[ny // 2, nx // 2]),
        float(lat[ny // 2, nx // 2]),
    )


def _relative_error(case: Case, scene: Scene, lon0: float, lat0: float) -> np.ndarray:
    result = travel_times(scene.bathymetry, lon0, lat0)
    exact = case.seconds(lon0, lat0, scene.lat, scene.lon)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.asarray(result.hours * 3600.0 / exact - 1.0)


def _bounds(
    case: Case, cells: np.ndarray, start_term: float
) -> tuple[float, np.ndarray]:
    """Return the lower bound and the upper bound per node of the relative error."""
    gap, lattice = _stencil_terms(case.cos_lat)
    lower = FACTOR - 1.0 - case.evaluation_error
    with np.errstate(divide="ignore"):
        upper = (
            FACTOR * (1.0 / math.cos(gap / 2) + (lattice + start_term) / cells)
            - 1.0
            + case.evaluation_error
        )
    return lower, upper


@pytest.mark.parametrize("node_offset", [0, 1])
@pytest.mark.parametrize("name", list(CASES))
def test_time_lies_between_the_exact_time_and_the_stencil_overshoot(
    name: str, node_offset: int
) -> None:
    case = CASES[name]
    scene = _scene(case, node_offset)

    error = _relative_error(case, scene, scene.lon0, scene.lat0)

    cells = scene.metres_from(scene.lon0, scene.lat0) / CELL_M
    lower, upper = _bounds(case, cells, 0.0)
    away = cells > 0
    assert error[away].min() >= lower
    assert (error[away] <= upper[away]).all()


@pytest.mark.parametrize("node_offset", [0, 1])
@pytest.mark.parametrize("name", list(CASES))
def test_time_along_a_meridian_is_exact_to_the_factor(
    name: str, node_offset: int
) -> None:
    case = CASES[name]
    scene = _scene(case, node_offset)
    column = scene.bathymetry.nx // 2

    error = _relative_error(case, scene, scene.lon0, scene.lat0)

    along = np.delete(error[:, column], scene.bathymetry.ny // 2)
    assert np.abs(along - (FACTOR - 1.0)).max() <= case.evaluation_error


@pytest.mark.parametrize("name", ["equator", "60 degrees"])
def test_epicenter_between_nodes_is_timed_from_the_epicenter(name: str) -> None:
    case = CASES[name]
    scene = _scene(case, 0)
    b = scene.bathymetry
    east, north = 0.37, -0.21
    lon0 = scene.lon0 + east * b.x_inc
    lat0 = scene.lat0 + north * b.y_inc

    error = _relative_error(case, scene, lon0, lat0)

    cells = scene.metres_from(lon0, lat0) / CELL_M
    start_term = _start_term(east, north, math.cos(math.radians(lat0)))
    lower, upper = _bounds(case, cells, start_term)
    assert error.min() >= lower
    assert (error <= upper).all()
