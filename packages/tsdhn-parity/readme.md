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

[Architecture](../../docs/architecture.md#where-the-code-is) lists the modules
and the per-unit parity directories under `packages/tsdhn/tests/parity/`.

Fixed-width readers use the declared field width instead of whitespace parsing.

See [Testing](../../docs/testing.md) for test selection and
[Parity](../../docs/parity.md) for the reference map.
