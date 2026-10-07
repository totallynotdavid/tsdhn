# tsdhn-parity

`tsdhn-parity` compares the Python engine with saved MATLAB runs and compiled
Fortran output. It is test support for compatibility checks.

## Run it

```sh
mise run test-parity
```

Saved MATLAB runs and Python cases do not need MATLAB. Fortran cases need
`TSDHN_TOOLS_DIR` to point to the compiled programs. Missing optional programs
skip their cases.

The active deformation executable must be built from `model/def_oka.f`.
`model/deform.for` is a separate Mansinha-Smylie implementation.

## Layout

- `tsdhn_parity/cases.py`: input-case generation.
- `tsdhn_parity/trace.py`: checkpoint and trace types.
- `tsdhn_parity/compare.py`: comparisons and tolerances.
- `tsdhn_parity/adapters/`: Python, Fortran, and saved-trace runners.
- `packages/tsdhn/tests/parity/<unit>/`: cases, readers, tolerances, and data.

The tsunami comparison gives both solvers the same fault-plane and deformation
result so it isolates propagation. Fixed-width readers use the declared field
width instead of whitespace parsing.

See [`../../docs/testing.md`](../../docs/testing.md) for test selection and
[`../../docs/legacy.md`](../../docs/legacy.md) for the active reference map.
