# tsdhn-ttt

`tsdhn-ttt` computes tsunami travel times in hours from one epicenter over a
bathymetry grid. It reads a GMT native 16-bit grid such as `cortado.i2` and
writes a GMT native float grid such as `ttt.b`.

## Run it

```sh
uv run tsdhn-ttt cortado.i2 -E-78.8/-12.0 -Tttt.b
```

Write a negative longitude as `-E-78.8/-12.0` or `--epicenter=-78.8/-12.0`. The
command exits with status 1 when the epicenter is on land or outside the grid.

From Python:

```python
from pathlib import Path

from tsdhn_ttt import read_bathymetry, travel_times, write_travel_times

bathymetry = read_bathymetry(Path("cortado.i2"))
result = travel_times(bathymetry, -78.8, -12.0)
write_travel_times(
    Path("ttt.b"),
    bathymetry,
    result.hours,
    (-78.8, -12.0),
    result.source_slope_s_per_km,
)
```

## Modes

The default is the most accurate configuration and is the one to use for
results. `--client-compatible` on the command line, or `client_compatible=True`
in `travel_times`, reproduces the compiled `ttt_client` instead. It exists to
compare the two programs, and the parity tests run in it.

| Setting              | Default                     | Client-compatible    |
| -------------------- | --------------------------- | -------------------- |
| Arithmetic           | `float64`                   | `float32`            |
| Segment length       | great circle between nodes  | start-row cosine     |
| Latitude of a cosine | cell centre (`node_offset`) | grid edge, no offset |
| Wavefront starts at  | the epicenter               | the nearest node     |
| `TravelTimes.hours`  | `float64`                   | `float32`            |

`write_travel_times` stores `float32` hours in both modes.

## Method

Wave speed is `sqrt(g * depth)`, with `g` taken from the latitude of each row.
Land and no-data cells block the wavefront. Each node reaches 120 neighbours up
to 13 cells away. The cost of a neighbour is the segment length times the mean
slowness along the segment. Dijkstra's algorithm settles nodes in order of
arrival. A settled node blocks any longer segment that crosses it, so results
depend on the order in which nodes settle. A final factor of `sqrt(sin f / f)`
with `f = 2 pi / 120`, 0.999772, removes the mean overshoot of the 120-direction
stencil.

Lengths are on a sphere of radius 6371007.181 m.

The default starts the wavefront at every water node within four cells of the
epicenter. Each starts at the straight-segment length from the epicenter times
the slowness interpolated along it, and a segment that meets land is dropped.
`ttt_client` instead starts at the nearest node, so it moves the source by up to
half a cell.

Water that the wavefront cannot reach is NaN, like land. Arrival times are in
hours, north row first.

## Accuracy

A path of stencil segments is never shorter than the geodesic. Times are
therefore later than the exact ones, and the factor above brings the mean back.
What remains is the stencil's: directions between two stencil directions cost
more than the straight line, more so where cells are narrow, and the whole
numbers of steps a path needs add a term that falls with distance.

`tests/test_ttt_accuracy.py` checks the default mode against exact great-circle
times in a uniform ocean at the equator and at 60 degrees, and in an ocean whose
speed is `a cos(latitude)`, whose exact time is known in every direction. A time
never falls below 0.999772 of the exact time. It never exceeds it by more than
the bound that the test derives from the stencil. The docstring of the test
gives the derivation.

`ttt_client` differs from the default in the rows of the table in
[Modes](#modes). It measures a segment that crosses rows with the cosine of its
start row, ignores the pixel offset of a `node_offset` 1 grid, and starts at the
nearest node, so its times differ from the default by more than the stencil
error. This command compares the two modes on `cortado.i2` for one epicenter:

```sh
uv run python - <<'EOF'
from pathlib import Path

import numpy as np

from tsdhn_ttt import read_bathymetry, travel_times

bathymetry = read_bathymetry(Path("model/ttt_mundo/cortado.i2"))
default = travel_times(bathymetry, -78.8, -12.0)
client = travel_times(bathymetry, -78.8, -12.0, client_compatible=True)
late = (client.hours - default.hours) * 3600.0
print(f"largest difference {np.nanmax(np.abs(late)):.0f} s")
print(f"mean client-compatible minus default {np.nanmean(late):+.1f} s")
EOF
```

It prints a largest difference of 130 s and a mean of +16.6 s, so the
client-compatible times are the later ones.

`tests/test_ttt_parity.py` runs the client-compatible mode against `ttt_client`
on nine epicenters of `model/ttt_mundo/cortado.i2` and on synthetic grids, and
requires times within 0.02 minutes.

## Limits

- Grids that span 360 degrees of longitude are rejected.
- Only the 16-bit input format is read. Header scaling is ignored.
- The reference is the sphere of the SDK. The Earth is an ellipsoid, whose
  distances differ from the sphere. Dispersion and nonlinearity are not
  modelled.
- The solver runs on one core. The first call compiles the kernel, and later
  calls reuse the cache.
