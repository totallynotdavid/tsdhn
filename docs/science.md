# Science

This page records what the engine computes: the inputs, the formulas and the
constants. Values inherited from the MATLAB and Fortran programs are called
compatibility rules. [Parity](parity.md) lists those programs.

## Inputs and source model

| Field  | Meaning                       | Unit or format                   |
| ------ | ----------------------------- | -------------------------------- |
| `Mw`   | Moment magnitude              | Dimensionless                    |
| `h`    | Hypocentral depth             | km                               |
| `lat0` | Epicenter latitude            | Decimal degrees, north positive  |
| `lon0` | Epicenter longitude           | Decimal degrees, east positive   |
| `hhmm` | Origin time                   | Four digits, UTC hour and minute |
| `dia`  | Day used in arrival-time text | Two characters                   |

The simulation uses one rectangular fault. Strike and dip come from the nearest
`mecfoc.dat` record. Rake is 90 degrees in the fault-plane stage.

Source dimensions and average slip use:

```text
L = 10^(0.55 Mw - 2.19) km
W = 10^(0.31 Mw - 0.63) km
M0 = 10^(1.5 Mw + 9.1) N m
mu = 4.0e10 N/m^2
L_m = L_km * 1000 m/km
W_m = W_km * 1000 m/km
D_m = M0 / (mu * L_m * W_m) m
```

`calculator.py` computes `D_m` from `M0` in N m, `mu` in N/m^2, and the
converted `L_m` and `W_m` in meters. The two `1000 m/km` conversions are part of
the current calculation.

The length and width relations come from Papazachos, B. C., Scordilis, E. M.,
Panagiotopoulos, D. G., Papazachos, C. B., and Karakaisis, G. F. (2004), "Global
relations between seismic fault parameters and moment magnitude of earthquakes",
Bulletin of the Geological Society of Greece 36, 1482-1489. The citation in the
code is the comment `Papazachos 2004` at `model/fault_plane.f90:40`. The
relations are implemented in `rupture_dimensions` in
`packages/tsdhn/tsdhn/calculator.py`, and the fault-plane stage and the preview
both call it. The comments name the authors and year only. The full reference
above is supplied here. `average_slip` in the same file solves the moment
magnitude relation for slip.

## Coordinate frames

Public inputs use `-180..180` longitude. The bathymetry axis and fault-plane
inputs use `0..360`. The fault-plane stage and the calculator preview both pick
the focal mechanism with `nearest_focal_mechanism`. It converts the epicenter
and the mechanism records to `0..360` and takes the longitude difference around
the circle, so the preview shows the strike and dip the run uses on either side
of the antimeridian and of the Greenwich meridian. The fault-plane stage also
converts the epicenter to `0..360` before it searches the bathymetry axes.

## Geodesy constants

The engine converts between degrees and distance with several different values.
They are not one model of the Earth. Each row is a value the code uses today.
Names are in `packages/tsdhn/tsdhn/constants.py` unless the row says otherwise.

| Value                  | Name and location                                                                           | Used for                                                                                                                           | Origin                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `111.0` km per degree  | `FAULT_PLANE_KILOMETERS_PER_DEGREE`; `model/physical_constants.inc:3` has the same constant | `fault_plane.py` (`_grid_window`, `_recompute_depth`) and the fault origin `xo`, `yo` in `calculator.py`                           | Origin not recorded                                                                          |
| `6371.0` km            | `MEAN_EARTH_RADIUS_KM`, which gives `MEAN_EARTH_KILOMETERS_PER_DEGREE` (111.1949)           | `calculate_distance_to_coast` in `utils/geo.py`: coast distance from the degree distance                                           | Named the mean Earth radius in the code; the choice of value is not recorded                 |
| `6370.8` km            | `TSUNAMI_MODEL_EARTH_RADIUS_KM`; no counterpart in `model/`                                 | `TsunamiCalculator._calculate_travel_time` in `calculator.py`: spherical distance to each port                                     | Origin not recorded                                                                          |
| `6.37e6` m             | `TSUNAMI_SOLVER_EARTH_RADIUS_M`; `model/physical_constants.inc:2` has the same constant     | `tsunami.py` (`_RT`): the solver's step coefficients                                                                               | Origin not recorded                                                                          |
| `111.1994` km          | `MAXOLA_GRID_KILOMETERS_PER_DEGREE`                                                         | `GridConfig.cellsize` in `render/maxola.py`: `7412.9951096 / 1000 / 111.1994` = 0.066664 degrees, where the solver spacing is 1/15 | Origin not recorded. The code does not say why this value differs from the solver's spacing. |
| `110` km per degree    | literal in `calculator.py` (`_calculate_travel_time`)                                       | Scales the path direction in the integrated arrival-time estimate                                                                  | Origin not recorded                                                                          |
| `7412.9951096` m       | `_DX` in `deform.py`; `GridConfig.dx` in `render/maxola.py`; `DX` at `model/def_oka.f:38`   | Grid spacing of the deformation grid and the maximum-height grid                                                                   | Origin not recorded. `model/deform.for:34` computes `240 * 1853 / 60`, which is 7412.0.      |
| `60 * 1853` m / degree | `NM_CONVERSION` in `calculator.py`                                                          | Converts fault-corner offsets to degrees in the displayed fault outline                                                            | Sixty nautical miles of 1853 m; the choice of 1853 is not recorded                           |

## Fault plane and deformation

The fault-plane stage reads `hypo.dat`, calculates dimensions and slip, selects
strike and dip, snaps the origin to the bathymetry axes, and writes the
deformation inputs. It truncates geographic window bounds before selecting the
nearest grid cell. It uses a 1.4 window multiplier for magnitudes above 8 and
2.8 otherwise.

`deform.py` follows the Okada-based `model/def_oka.f` calculation for one
rectangular segment. Inputs use meters and degrees. The grid spacing is
`7412.9951096 m` on both axes. The arrays are float32, and singular branches use
an epsilon of `1e-8`. The exact `deform_a.grd` field layout is documented in
[`pipeline.md`](pipeline.md), alongside the other stage-file formats.

### Legacy substitutions

Three rules replace a computed value with a fixed one. All three come from the
Fortran programs, and the Python code reproduces them.

| Rule                                                            | Fortran                                                      | Python                                                                | Effect                                                                                                               | Rationale    |
| --------------------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------------ |
| A negative upper-edge depth becomes 5000 m                      | `model/fault_plane.f90:108-110`                              | `_recompute_depth` in `fault_plane.py`                                | A fault whose upper edge would lie above the surface is placed at 5 km depth. The computed depth is discarded.       | Not recorded |
| Strike 0 or 360 degrees gets 0.001 degrees added                | `model/def_oka.f:77-78`                                      | `compute_deform_grid` in `deform.py`                                  | A strike of exactly 0 or 360 is computed as 0.001 or 360.001. The code comment says it avoids a singular transform.  | Not recorded |
| A grid value with an absolute value of 20 m or more is set to 0 | `model/def_oka.f:150-153` (the Fortran also prints the cell) | `clip_anomalous_values` in `deform.py`, which logs a warning per call | The deformation grid never holds a vertical displacement of 20 m or more. The cell becomes 0, not a clamped maximum. | Not recorded |

## Propagation

`tsunami.py` follows the active linear shallow-water calculation in
`model/tsunami1.for`:

| Quantity        |                                         Value |
| --------------- | --------------------------------------------: |
| Grid shape      |                            2461 by 2056 cells |
| Angular spacing |                240 arcseconds, or 1/15 degree |
| Time step       |                                     3 seconds |
| Number of steps |                                        33,602 |
| Gauge sampling  |                 Every 20 steps, or 60 seconds |
| Gauges          |                                            17 |
| Earth radius    |  `TSUNAMI_SOLVER_EARTH_RADIUS_M` = `6.37e6 m` |
| Gravity         | `STANDARD_GRAVITY_M_PER_S2` = `9.80665 m/s^2` |

Positive bathymetry values are water depths. Negative values are land. Water
depths below 10 m are raised to 10 m before integration. The solver updates
continuity, boundary radiation, momentum, sampled gauges, and maximum elevation
in that order. It preserves float32 evaluation order and fixed-width output
quantization.

## Arrival-time estimates

The CLI's port arrival times are separate from the propagation solver. The
`TsunamiCalculator._calculate_travel_time` method in
`packages/tsdhn/tsdhn/calculator.py` applies these current rules:

1. Calculate spherical distance with `TSUNAMI_MODEL_EARTH_RADIUS_KM`.
2. For distances at least 750 km, use `distance / 790 + 0.2` hours.
3. For epicenters outside `-19 <= lat0 <= 0`, use `distance / 700` hours.
4. Otherwise, sample 101 evenly spaced points along the path. At each point,
   construct the path direction as
   `([port_lon - lon0, port_lat - lat0] / distance) * 110`, where 110 is the
   km-per-degree path factor. Add the 101 values of
   `index * (degrees(alpha) / 100) * direction` to `[lon0, lat0]`, then sample
   bathymetry at each `(lat, lon)` point. Take the absolute depth, convert
   `sqrt(STANDARD_GRAVITY_M_PER_S2 * depth)` from
   `packages/tsdhn/tsdhn/constants.py`, convert it to km/h by multiplying by
   3.6, and integrate reciprocal speed with Simpson's rule. The travel time is
   half of that integral.
5. For the integrated result, replace times above 3.0 hours with
   `distance / 733 + 0.25`, and times strictly between 1.4 and 3.0 hours with
   `distance / 690 + 0.2`. Times at or below 1.4 hours remain integrated.

The speeds (790, 700, 733 and 690), the offsets (0.2 and 0.25 hours) and the
thresholds (750 km, 1.4 and 3.0 hours) are empirical. Their origin is not
recorded, and neither the code nor `model/` explains them.

The origin time is added after these rules in decimal hours. The separate
`ttt_client` stage produces the arrival-time grid used by `ttt.pdf`.

## Report transformations

`maxola` flips and rescales the sampled maximum grid so the largest displayed
value is 12 m. `ttt_max` applies station-specific fourth-root factors before
writing corrected series and summaries. The factors are listed in
`packages/tsdhn/tsdhn/render/ttt_max.py`; their origin is not recorded. Neither
transformation changes the solver values in `zfolder/green.dat` or
`zfolder/zmax_a.grd`.
