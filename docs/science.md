# Scientific and numerical assumptions

This guide records what the current engine computes. Values inherited from the
comparison programs are identified as compatibility rules.

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

The active Fortran source attributes the dimension relations to Papazachos et
al. (2004). The repository does not include the paper or a full citation.

## Coordinate frames

Public inputs use `-180..180` longitude. The bathymetry axis and fault-plane
inputs use `0..360`. The fault-plane stage adds 360 to negative longitudes
before searching the mechanism and bathymetry files. The calculator preview
converts mechanism records to the public frame.

Fault placement uses 111.0 km per degree. Displayed fault corners use
`60 * 1853 m` per degree. These are the current calculation rules, not a general
geodesic model.

## Fault plane and deformation

The fault-plane stage reads `hypo.dat`, calculates dimensions and slip, selects
strike and dip, snaps the origin to the bathymetry axes, and writes the
deformation inputs. It truncates geographic window bounds before selecting the
nearest grid cell. It uses a 1.4 window multiplier for magnitudes above 8 and
2.8 otherwise. A negative upper-edge depth becomes 5000 m.

`deform.py` follows the Okada-based `model/def_oka.f` calculation for one
rectangular segment. Inputs use meters and degrees. The grid spacing is
`7412.9951096 m` on both axes. Compatibility behavior includes float32 arrays,
an epsilon of `1e-8` for singular branches, a 0.001 degree offset for strike 0
or 360, and zeroing values whose absolute magnitude is at least 20 m. The exact
`deform_a.grd` field layout is documented in [`pipeline.md`](pipeline.md),
alongside the other stage-file formats.

## Propagation

`tsunami.py` follows the active linear shallow-water calculation in
`model/tsunami1.for`:

| Quantity        |                          Value |
| --------------- | -----------------------------: |
| Grid shape      |             2461 by 2056 cells |
| Angular spacing | 240 arcseconds, or 1/15 degree |
| Time step       |                      3 seconds |
| Number of steps |                         33,602 |
| Gauge sampling  |  Every 20 steps, or 60 seconds |
| Gauges          |                             17 |
| Earth radius    |                     `6.37e6 m` |
| Gravity         |                    `9.8 m/s^2` |

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
   `sqrt(9.81 * depth)` using `STANDARD_GRAVITY_M_PER_S2` from
   `packages/tsdhn/tsdhn/constants.py`, convert it to km/h by multiplying by
   3.6, and integrate reciprocal speed with Simpson's rule. The travel time is
   half of that integral.
5. For the integrated result, replace times above 3.0 hours with
   `distance / 733 + 0.25`, and times strictly between 1.4 and 3.0 hours with
   `distance / 690 + 0.2`. Times at or below 1.4 hours remain integrated.

The origin time is added after these rules in decimal hours. The separate
`ttt_client` stage produces the arrival-time grid used by `ttt.pdf`.

## Report transformations

`maxola` flips and rescales the sampled maximum grid so the largest displayed
value is 12 m. `ttt_max` applies station-specific fourth-root factors before
writing corrected series and summaries. Neither transformation changes the
solver values in `zfolder/green.dat` or `zfolder/zmax_a.grd`.
