# Model files

This directory holds the model inputs and the Fortran programs that the parity
tests compare the Python engine with. The engine does not run the programs.

## Reference programs

| File              | Role                                                             |
| ----------------- | ---------------------------------------------------------------- |
| `fault_plane.f90` | Fault placement, source dimensions, slip, and intermediate files |
| `def_oka.f`       | Okada-based deformation                                          |
| `tsunami1.for`    | Linear shallow-water propagation                                 |
| `deform.for`      | Mansinha-Smylie deformation, not used by the comparison          |

`make -C model OUT=<directory>` builds `def_oka.f` as `deform`, `fault_plane`
and `tsunami` with Intel `ifx`. `scripts/setup.sh` installs the compiler and
runs that command. [Parity](../docs/parity.md) maps each program to its Python
stage.

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
was derived from the GEBCO `GridOne.nc` grid. They need `csh` and GMT, and run
in this order:

1. `pacifico.csh` cuts and resamples two regions of `GridOne.nc` to 240
   arcseconds, joins them with `cat` and `awk`, and writes `pacifico.grd` for
   120/300/-80/89 with `gmt xyz2grd`.
2. `make_etopo_i2` combines `pacifico.grd` with a land-sea mask, clips values
   above -1 to -1 and writes `cortado.i2`. It deletes `pacifico.grd` when it
   finishes.

The path to `GridOne.nc` is the only line to edit: the `BATHYFILE0` variable at
the top of `pacifico.csh`. The checked-in `cortado.i2` is used as is.

A run writes `pfalla.inp`, `xyo.dat`, `meca.dat` and `zfolder/*` to its run
directory, so they are not tracked here. The tests read sample `meca.dat`,
`pfalla.inp` and `deform_a.grd` files from `packages/tsdhn/tests/data/`.
[Pipeline](../docs/pipeline.md) gives the formats.
