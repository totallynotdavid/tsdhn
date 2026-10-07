# Simulation pipeline

This guide follows one researcher run from its input files to its reports. The
engine validates the model directory, prepares a run directory, and executes the
registered stages in order. A stage is skipped on resume only when its
completion marker and every declared output are valid.

## Stage map

| Stage          | Reads                                              | Writes                                                   | Output use                            |
| -------------- | -------------------------------------------------- | -------------------------------------------------------- | ------------------------------------- |
| `fault_plane`  | `hypo.dat`, mechanism and bathymetry inputs        | `pfalla.inp`, `xyo.dat`, `meca.dat`                      | Fault geometry and deformation inputs |
| `deform`       | `pfalla.inp`, `xyo.dat`                            | `deform_a.grd`                                           | Initial sea-surface displacement      |
| `tsunami`      | bathymetry, deformation, and tide inputs           | `zfolder/green.dat`, `zfolder/zmax_a.grd`                | Sampled gauges and maximum elevation  |
| `maxola`       | `zfolder/zmax_a.grd`, mechanism and station inputs | `maxola.pdf`                                             | Maximum-height display map            |
| `ttt_max`      | `zfolder/green.dat`                                | `zfolder/green_rev.dat`, `ttt_max.dat`, `mareograma.svg` | Corrected station reports             |
| `ttt_inverso`  | mechanism and travel-time grid inputs              | `ttt_mundo/ttt.b`                                        | Arrival-time grid                     |
| `point_ttt`    | `ttt_mundo/ttt.b` and map inputs                   | `ttt_mundo/ttt.pdf`                                      | Arrival-time map                      |
| `copy_ttt_pdf` | `ttt_mundo/ttt.pdf`                                | `ttt.pdf`                                                | Root-level arrival-time report        |

The first five stages run in the run root. The travel-time map stages use
`ttt_mundo`.

## Input and intermediate files

`hypo.dat` stores origin time, longitude, latitude, hypocentral depth, and
moment magnitude. `pfalla.inp` stores one-based grid indices, slip, fault
dimensions, angles, and top-edge depth. `xyo.dat` stores one-based inclusive
grid bounds and the full grid dimensions. `meca.dat` is a fixed-width mechanism
record whose longitude uses the `0..360` frame.

### `pfalla.inp`

The fault-plane writer emits one whitespace-separated record with nine fields.
The current Python writer uses variable-width numeric text, not a fixed-width
format; the Fortran readers use list-directed input and accept the same layout.

| Position | Field | Unit or format                            |
| -------- | ----- | ----------------------------------------- |
| 1        | `I0`  | One-based full-grid column index, integer |
| 2        | `J0`  | One-based full-grid row index, integer    |
| 3        | `D0`  | Average dislocation, meters               |
| 4        | `L0`  | Fault length along strike, meters         |
| 5        | `W0`  | Fault width down dip, meters              |
| 6        | `ST`  | Strike, degrees                           |
| 7        | `DI`  | Dip, degrees                              |
| 8        | `SL`  | Rake, degrees; the active writer uses 90  |
| 9        | `HH`  | Top-edge depth, meters                    |

The field order is therefore:

```text
I0 J0 D0 L0 W0 ST DI SL HH
```

The deformation reader consumes all nine fields. A legacy sample may wrap the
record across display lines, but whitespace separates the fields.

### `xyo.dat`

The writer emits six whitespace-separated integer fields with variable width:

```text
IDS IDE JDS JDE IA JA
```

`IDS`, `IDE`, `JDS`, and `JDE` are one-based inclusive full-grid bounds. `IA`
and `JA` are the full grid dimensions, currently 2461 and 2056. The deformation
and tsunami readers consume only the first four fields; `IA` and `JA` are legacy
trailing padding retained in the generated file.

### `meca.dat`

`meca.dat` is one fixed-width record written with the Fortran layout
`(7f7.2 A5 A4)`. The record has these fields:

| Columns | Value                                       | Format or unit  |
| ------- | ------------------------------------------- | --------------- |
| 1-7     | Longitude in the `0..360` frame             | `F7.2`          |
| 8-14    | Latitude                                    | `F7.2`, degrees |
| 15-21   | Hypocentral depth                           | `F7.2`, km      |
| 22-28   | Strike                                      | `F7.2`, degrees |
| 29-35   | Dip                                         | `F7.2`, degrees |
| 36-42   | Rake                                        | `F7.2`, degrees |
| 43-49   | Moment magnitude                            | `F7.2`          |
| 50-54   | Two zero-valued plotting coordinates, `0 0` | `A5`            |
| 55-58   | Event time `hhmm`                           | `A4`            |

The record has ten whitespace-separated values when read as text, even though
the two plotting values share the `A5` field.

### `deform_a.grd`

`deform_a.grd` contains one fixed-width `%9.3f` displacement field per grid
cell. There are `JDE - JDS + 1` values per row and `IDE - IDS + 1` rows for the
window in `xyo.dat`. Fields have no separator beyond their nine-column width,
and values are in meters. The tsunami reader parses all fields as float32 and
rejects a file whose value count does not equal that window size.

### `green.dat`

The active Python writer emits one seven-column time field followed by one
seven-column elevation field per actual gauge. With the current 17 gauges, each
row has the layout `(F7.1, 17F7.3)`. Time is minutes from the origin with one
decimal place, and each virtual-gauge elevation is in meters with three decimal
places. The solver writes a row every 20 solver steps (`20 * 3 s = 60 s`).

The legacy Fortran declaration is `(F7.1, 100F7.3)`. It reserves capacity for
100 elevation fields, but it is not the active Python-written layout.

`zmax_a.grd` contains the greatest positive elevation seen at each 60-second
sample. It is not updated at every solver step.

### Tsunami checkpoint

`zfolder/_checkpoint.npz` stores `pipeline_version`, the last fully completed
step `k`, the two elevation buffers `z1` and `z2`, the two momentum buffers `m1`
and `m2`, the two discharge buffers `n1` and `n2`, the sampled maximum grid
`zmxa`, and the sampled `gauge_minutes` and `gauge_values` rows. The current
checkpoint interval is 2,000 solver steps.

The tsunami reader accepts a checkpoint only when all of these checks pass:

1. `pipeline_version` equals `PIPELINE_VERSION` from
   `packages/tsdhn/tsdhn/pipeline_version.py`.
2. Each of `z1`, `z2`, `m1`, `m2`, `n1`, `n2`, and `zmxa` has shape `(IA, JA)`
   and dtype `float32`.
3. If `gauge_values` has rows, its second dimension equals the current gauge
   count.
4. `k` is between zero and `KE`, inclusive.
5. The saved gauge minutes and gauge rows can be paired one-to-one.

Missing, unreadable, stale-version, wrong-shape, wrong-dtype, wrong-gauge,
out-of-range, or mismatched gauge-row checkpoints are logged as unusable and the
run starts at step zero. A successful run removes the checkpoint after writing
the final fixed-width outputs.

## Raw values and reports

| File                    | Value type             | Transformation                                 |
| ----------------------- | ---------------------- | ---------------------------------------------- |
| `deform_a.grd`          | Quantized stage output | Three decimal places                           |
| `zfolder/green.dat`     | Sampled solver values  | Every 60 seconds, three decimal places         |
| `zfolder/zmax_a.grd`    | Sampled solver maximum | Every 60 seconds, three decimal places         |
| `zfolder/green_rev.dat` | Report values          | Station-specific empirical factors             |
| `ttt_max.dat`           | Report summary         | Corrected station values                       |
| `mareograma.svg`        | Report plot            | Corrected station values and display scale     |
| `maxola.pdf`            | Display map            | Grid values rescaled to a 12 m display maximum |

Use `zfolder/green.dat` and `zfolder/zmax_a.grd` for solver values. The PDF,
SVG, and corrected station files are report products.

## Resume behavior

The tsunami checkpoint stores both elevation buffers, both momentum buffers, the
sampled maximum grid, gauge rows, and the last completed step. It is written
after a buffer swap, so a resumed run starts at a complete step. A
pipeline-version change is required when the meaning or order of saved state
changes.

The engine runs the tsunami stage in a workspace that can be reused after a
worker restart. The compute service's workspace lock and job rules are in
[`jobs.md`](jobs.md).

## Find the implementation

| Behavior                                | Code                                        |
| --------------------------------------- | ------------------------------------------- |
| Source parameters and arrival estimates | `packages/tsdhn/tsdhn/calculator.py`        |
| Fault geometry and input files          | `packages/tsdhn/tsdhn/fault_plane.py`       |
| Deformation                             | `packages/tsdhn/tsdhn/deform.py`            |
| Propagation and checkpoints             | `packages/tsdhn/tsdhn/tsunami.py`           |
| Stage order                             | `packages/tsdhn/tsdhn/pipeline/registry.py` |
| Report transformations                  | `packages/tsdhn/tsdhn/render/`              |
| Run setup and output collection         | `packages/tsdhn/tsdhn/engine.py`            |
