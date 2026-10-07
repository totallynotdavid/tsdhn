# Model files

This directory contains model inputs and the programs used by the active
compatibility comparisons.

## Reference programs

| File              | Role                                                             |
| ----------------- | ---------------------------------------------------------------- |
| `fault_plane.f90` | Fault placement, source dimensions, slip, and intermediate files |
| `def_oka.f`       | Okada-based deformation comparison                               |
| `tsunami1.for`    | Linear shallow-water propagation comparison                      |
| `deform.for`      | Mansinha-Smylie deformation implementation                       |

The active deformation comparison builds `def_oka.f` as `deform`. The Python
engine does not use the compiled programs for normal simulation runs.

## Model inputs

| Path                           | Use                             |
| ------------------------------ | ------------------------------- |
| `bathy/grid_a.grd`             | Propagation bathymetry          |
| `bathy/xa.dat`, `bathy/ya.dat` | Grid axes for fault placement   |
| `mecfoc.dat`                   | Candidate focal mechanisms      |
| `tidal.dat`                    | Virtual-gauge indices           |
| `pacifico.mat`, `maper1.mat`   | Bathymetry and coastline data   |
| `ttt_mundo/`                   | Inputs for `ttt_client` and GMT |

Intermediate files such as `pfalla.inp`, `xyo.dat`, `meca.dat`, and `zfolder/*`
are generated during a run. Their formats are in
[`../docs/pipeline.md`](../docs/pipeline.md). Comparison limits are in
[`../docs/legacy.md`](../docs/legacy.md).
