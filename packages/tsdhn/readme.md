# tsdhn

`tsdhn` is the simulation engine and researcher CLI. The CLI, API, and worker
run the same Python pipeline. The [root README](../../readme.md#install) covers
installation and a first run.

## Commands

| Command                | Purpose                                          |
| ---------------------- | ------------------------------------------------ |
| `tsdhn assets install` | Download and install the versioned model data    |
| `tsdhn assets status`  | Print the install state of a model version       |
| `tsdhn doctor`         | Report the model data and external tools         |
| `tsdhn calc`           | Preview source parameters and port arrival times |
| `tsdhn run`            | Run the complete pipeline                        |

`calc` and `run` take `--mw` (default 9.0), `--lat` (-20.5), `--lon` (-70.5),
`--depth` in km (12.0), `--time` as HHMM UTC (0000) and `--day` of the month
(23). Use `--model-version` to select an installed dataset and `--model-dir` to
use a specific directory. `run` also takes `--work-dir` to choose the run
directory. Run `uv run tsdhn run --help` for every option.

## Model files

Model files resolve in this order:

1. `--model-dir`.
2. `TSDHN_MODEL_DIR`.
3. The installed model version.

`tsdhn assets install` stores a versioned archive under
`$XDG_DATA_HOME/tsdhn/models`, or `$HOME/.local/share/tsdhn/models` when
`XDG_DATA_HOME` is unset. `TSDHN_DATA_HOME` takes precedence over both and
selects the data root itself.

The report stages use GMT and `ttt_client`. [Parity](../../docs/parity.md)
covers the Fortran programs used for comparison.

## Outputs

| File                 | Meaning                                         |
| -------------------- | ----------------------------------------------- |
| `input.json`         | The parameters of the run                       |
| `runtime.json`       | Model version, model directory and tool status  |
| `calculation.json`   | Source parameters and fault rectangle           |
| `travel_times.json`  | Port arrival times and distances                |
| `travel_times.csv`   | The same arrival times as CSV                   |
| `zfolder/green.dat`  | Sampled solver elevations at virtual gauges     |
| `zfolder/zmax_a.grd` | Sampled maximum positive solver elevation       |
| `maxola.pdf`         | Display map made from the maximum grid          |
| `ttt.pdf`            | Arrival-time map made with `ttt_client` and GMT |
| `mareograma.svg`     | Selected station series after report scaling    |

The run collects `maxola.pdf`, `ttt.pdf` and `mareograma.svg` only when the
report stages produced them.

[Pipeline](../../docs/pipeline.md) describes the raw solver files and the report
transformations. [Science](../../docs/science.md) states the numerical rules.
[Architecture](../../docs/architecture.md#where-the-code-is) lists where each
part of the engine lives.
