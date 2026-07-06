# tsdhn-cli

`tsdhn-cli` is a Typer/Rich command-line client for running TSDHN calculations
directly through `tsdhn-core`. It does not call the FastAPI service.

## Commands

```sh
uv run tsdhn calc
uv run tsdhn run
uv run tsdhn steps
```

| Command | Purpose |
| --- | --- |
| `calc` | Calculate source parameters and tsunami travel times without running the full pipeline |
| `run` | Execute the full simulation pipeline in a local work directory |
| `steps` | Print the names accepted by `run --skip` |

## Runtime requirements

`calc` needs `TSDHN_MODEL_DIR` because `TsunamiCalculator` loads model assets.

`run` needs `TSDHN_MODEL_DIR` and `TSDHN_TOOLS_DIR` unless every command step
that requires prebuilt model executables is skipped.

## Examples

Preview calculations:

```sh
uv run tsdhn calc \
  --mw 9.0 \
  --depth 12.0 \
  --lat -20.5 \
  --lon -70.5 \
  --time 0000 \
  --day 23
```

Run the full pipeline:

```sh
uv run tsdhn run \
  --mw 9.0 \
  --depth 12.0 \
  --lat -20.5 \
  --lon -70.5 \
  --time 0000 \
  --day 23 \
  --work-dir jobs/manual-run
```

List skip-step names:

```sh
uv run tsdhn steps
```

Skip a step during local diagnosis:

```sh
uv run tsdhn run --skip generate_reports
```

`--skip` is repeatable.

> [!CAUTION]
> Skipping pipeline steps changes the generated artifacts and can invalidate a
> simulation result. Use skipped runs only for technical diagnosis.

## Development

From the repository root:

```sh
uv run tsdhn --help
uv run --package tsdhn-cli python -m cli.main --help
```
