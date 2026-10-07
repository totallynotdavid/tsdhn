# tsdhn

`tsdhn` is the simulation engine and researcher CLI. The CLI, API, and worker
run the same Python pipeline.

## Run it

Install model files and check external tools:

```sh
mise run install
uv run tsdhn assets install
uv run tsdhn doctor
```

Preview source parameters and port arrival-time estimates:

```sh
uv run tsdhn calc --mw 8.0 --lat -20.5 --lon -70.5
```

Run the complete pipeline:

```sh
uv run tsdhn run --mw 8.0 --lat -20.5 --lon -70.5
```

Use `--model-version` to select an installed dataset, `--model-dir` to use a
specific directory, and `--work-dir` to choose the run directory.

## Model files

Model files resolve in this order:

1. `--model-dir`.
2. `TSDHN_MODEL_DIR`.
3. The installed model version.

`tsdhn assets install` stores a versioned archive under
`$XDG_DATA_HOME/tsdhn/models`, or `$HOME/.local/share/tsdhn/models` when
`XDG_DATA_HOME` is unset. `TSDHN_DATA_HOME` selects another data root.

The report stages use GMT and `ttt_client`. The older Fortran programs are used
by comparison tests.

## Outputs

| File                 | Meaning                                         |
| -------------------- | ----------------------------------------------- |
| `calculation.json`   | Source parameters and fault rectangle           |
| `travel_times.json`  | Port arrival times and distances                |
| `zfolder/green.dat`  | Sampled solver elevations at virtual gauges     |
| `zfolder/zmax_a.grd` | Sampled maximum positive solver elevation       |
| `maxola.pdf`         | Display map made from the maximum grid          |
| `ttt.pdf`            | Arrival-time map made with `ttt_client` and GMT |
| `mareograma.svg`     | Selected station series after report scaling    |

The raw solver files and report transformations are described in
[`../../docs/pipeline.md`](../../docs/pipeline.md). Numerical rules are in
[`../../docs/science.md`](../../docs/science.md).

## Code map

- `tsdhn/calculator.py`: source parameters and port arrival times.
- `tsdhn/fault_plane.py`: fault placement and stage input files.
- `tsdhn/deform.py`: Okada-based deformation calculation.
- `tsdhn/tsunami.py`: shallow-water solver and checkpoints.
- `tsdhn/pipeline/`: stage definitions and order.
- `tsdhn/render/`: maps, station summaries, and report transformations.
- `tsdhn/engine.py`: run setup, stage execution, resume, and output collection.
- `tsdhn/runtime.py`: model validation and external-program checks.
- `tsdhn/assets.py`: versioned model installation.
- `tsdhn/cli/`: researcher commands.

Service deployment is documented in
[`../../docs/deploy.md`](../../docs/deploy.md). System boundaries are documented
in [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md).
