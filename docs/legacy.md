# Compatibility references

The active comparison references identify file formats, numerical ordering, and
behavior preserved by the Python implementation. Matching a reference is
compatibility evidence. It does not establish scientific validity.

## Active reference map

| Python code                          | Reference               | Comparison use                                |
| ------------------------------------ | ----------------------- | --------------------------------------------- |
| `calculator.py` and source relations | `model/fault_plane.f90` | Source dimensions, slip, and mechanism values |
| `fault_plane.py`                     | `model/fault_plane.f90` | Fault placement and intermediate files        |
| `deform.py`                          | `model/def_oka.f`       | Okada-based deformation                       |
| `tsunami.py`                         | `model/tsunami1.for`    | Linear shallow-water propagation              |
| Python checkpoints                   | Saved MATLAB traces     | Selected intermediate values                  |

`model/deform.for` implements a different Mansinha-Smylie deformation model. The
active deformation comparison uses `model/def_oka.f`, which `scripts/setup.sh`
and `model/Makefile` build as `deform`.

## Preserved behavior

The Python stages preserve these comparison-visible details:

- mixed longitude frames between public inputs and model grids;
- one-based grid indices in intermediate files;
- integer truncation before fault-window snapping;
- a fixed 90-degree rake in the fault-plane path;
- float32 calculation in deformation and propagation;
- singular branches in the Okada calculation;
- fixed grid, time-step, sampling, and update-order constants;
- fixed-width output fields and decimal quantization.

The Python propagation stage writes the active grid-A outputs used by the
current pipeline and resumable checkpoints. Checkpoint state is operational
state and is not part of the Fortran result.

## Compare a change

Run the comparison suite with:

```sh
mise run test-parity
```

The tsunami comparison gives both solvers the same fault-plane and deformation
inputs, so it isolates propagation. The suite does not independently compare the
complete chain as two separate production runs. Tolerances account for float32
rounding and fixed-width quantization.
