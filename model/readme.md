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

`make -C model OUT=<directory>` builds `deform`, `fault_plane` and `tsunami`
with Intel `ifx`; `scripts/setup.sh` installs the compiler and runs that
command.

## Model inputs

| Path                           | Use                              |
| ------------------------------ | -------------------------------- |
| `bathy/grid_a.grd`             | Propagation bathymetry           |
| `bathy/xa.dat`, `bathy/ya.dat` | Grid axes for fault placement    |
| `mecfoc.dat`                   | Candidate focal mechanisms       |
| `tidal.dat`                    | Virtual-gauge indices            |
| `pacifico.mat`, `maper1.mat`   | Bathymetry and coastline data    |
| `ttt_mundo/cortado.i2`         | Bathymetry grid for `ttt_client` |

`ttt_mundo/pacifico.csh` and `ttt_mundo/make_etopo_i2` record how `cortado.i2`
was derived from the GEBCO `GridOne.nc` grid, whose path is set at the top of
`pacifico.csh`. No script here converts the `salida.xyz` that `pacifico.csh`
writes into the `pacifico.grd` that `make_etopo_i2` reads, so the pair does not
rebuild the grid on its own. The checked-in grid is used as is.

Intermediate files such as `pfalla.inp`, `xyo.dat`, `meca.dat`, and `zfolder/*`
are generated during a run and are not tracked. The tests read the sample
`meca.dat`, `pfalla.inp` and `deform_a.grd` from `packages/tsdhn/tests/data/`.
Their formats are in [`../docs/pipeline.md`](../docs/pipeline.md). Comparison
limits are in [`../docs/legacy.md`](../docs/legacy.md).
