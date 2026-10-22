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

## Method

Wave speed is `sqrt(g * depth)`, with `g` taken from the latitude of each row.
Land and no-data cells block the wavefront. Each node reaches 120 neighbours up
to 13 cells away. The cost of a neighbour is the segment length times the mean
slowness along the segment. Dijkstra's algorithm settles nodes in order of
arrival. A settled node blocks any longer segment that crosses it, so results
depend on the order in which nodes settle. A final factor of 0.99977 removes the
mean bias of the 120-direction stencil.

Arrival times are `float32` hours, north row first. Water that the wavefront
cannot reach is NaN, like land.

## Limits

- Grids that span 360 degrees of longitude are rejected.
- Only the 16-bit input format is read. Header scaling is ignored.
- The solver runs on one core. The first call compiles the kernel, and later
  calls reuse the cache.
