# tsdhn-parity

`tsdhn-parity` compares the Python engine with saved MATLAB runs and compiled
Fortran output. It is test support for compatibility checks.

## Run it

```sh
mise run test-parity
```

Saved MATLAB runs and Python cases do not need MATLAB. Fortran cases need
`TSDHN_TOOLS_DIR` to point to the compiled programs and are skipped without
them. Build the `deform` executable from `model/def_oka.f`.

## Layout

- `tsdhn_parity/cases.py`: input-case generation.
- `tsdhn_parity/trace.py`: checkpoint and trace types.
- `tsdhn_parity/compare.py`: comparisons and tolerances.
- `tsdhn_parity/adapters/`: Python, Fortran, and saved-trace runners.
- `packages/tsdhn/tests/parity/<unit>/`: cases, readers, tolerances, and data.

Fixed-width readers use the declared field width instead of whitespace parsing.

See [Testing](../../docs/testing.md) for test selection and
[Parity](../../docs/parity.md) for the reference map.
