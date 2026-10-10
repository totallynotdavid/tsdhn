# Parity

The Python stages are compared with the MATLAB and Fortran programs they
replace. A match shows that Python reproduces the reference within a tolerance.
It does not show that the reference is physically right.

## Reference map

| Python code                          | Reference               | Compared                                      |
| ------------------------------------ | ----------------------- | --------------------------------------------- |
| `calculator.py` and source relations | `model/fault_plane.f90` | Source dimensions, slip, and mechanism values |
| `fault_plane.py`                     | `model/fault_plane.f90` | Fault placement and intermediate files        |
| `deform.py`                          | `model/def_oka.f`       | Okada-based deformation                       |
| `tsunami.py`                         | `model/tsunami1.for`    | Linear shallow-water propagation              |
| Python checkpoints                   | Saved MATLAB traces     | Selected intermediate values                  |

`model/deform.for` is a different, Mansinha-Smylie deformation model. The
comparison uses `model/def_oka.f`, which `scripts/setup.sh` and `model/Makefile`
build as `deform`.

## Preserved behavior

The Python stages keep these details of the references:

- mixed longitude frames between public inputs and model grids;
- one-based grid indices in intermediate files;
- integer truncation before fault-window snapping;
- a fixed 90-degree rake in the fault-plane path;
- float32 calculation in deformation and propagation;
- singular branches in the Okada calculation;
- fixed grid, time-step, sampling and update-order constants;
- fixed-width output fields and decimal quantization.

[Science](science.md) states the numerical rules and [Pipeline](pipeline.md) the
file formats. [Science](science.md#legacy-substitutions) lists the rules that
replace a computed value with a fixed one.

Checkpoint state is Python's own and has no Fortran counterpart.

## Run the comparison

```sh
mise run test-parity
```

Python cases and the saved MATLAB traces need no extra tools. Fortran cases need
the compiled programs in `TSDHN_TOOLS_DIR` and are skipped without them.

The tsunami comparison gives both solvers the same fault-plane and deformation
inputs, so it isolates propagation. It does not compare two complete production
runs. Tolerances allow for float32 rounding and fixed-width quantization.

## Refresh the MATLAB traces

The saved traces are captured evidence. A refresh records the input case, the
source, the checkpoint names and the reason for the new capture.

```sh
uv run python scripts/capture_matlab_fixtures.py fault_plane
```

The script runs MATLAB in a container and needs the MathWorks image and a
license. `mise run parity-capture-matlab` runs the same script. The comparison
code is described in
[`packages/tsdhn-parity`](../packages/tsdhn-parity/readme.md).
