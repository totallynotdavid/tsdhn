# tsdhn-core

`tsdhn-core` is the simulation package shared by the API and CLI. It contains
earthquake source calculations, tsunami travel-time calculations, runtime path
validation, workspace preparation, and the ordered TSDHN processing pipeline.

The API service and CLI both depend on this package. The core does not import
FastAPI, Redis, RQ, Typer, or web application code.

## Public interfaces

| Interface | Location | Purpose |
| --- | --- | --- |
| `EarthquakeInput` | [`core/schemas.py`](./core/schemas.py) | Validated earthquake input shared by API, CLI, and web client types |
| `TsunamiCalculator` | [`core/calculator.py`](./core/calculator.py) | Source-parameter and travel-time calculations |
| `run_simulation()` | [`core/simulation.py`](./core/simulation.py) | Full pipeline execution in a work directory provided by the caller |
| `RuntimePaths` | [`core/runtime.py`](./core/runtime.py) | Model/tool path resolution and validation |
| `MASTER_PIPELINE` | [`core/config.py`](./core/config.py) | Ordered processing steps used by API worker and CLI runs |

## Runtime paths

`TsunamiCalculator()` loads model assets during initialization. Without an
explicit `model_dir`, it reads `TSDHN_MODEL_DIR`.

`run_simulation()` resolves runtime paths with `RuntimePaths.resolve()`:

- `model_dir` argument, or `TSDHN_MODEL_DIR`.
- `tools_dir` argument, or `TSDHN_TOOLS_DIR` when active command steps need
  prebuilt model executables.

The model directory must contain these directories:

```txt
bathy/
ttt_mundo/
```

It must also contain these files:

```txt
pacifico.mat
maper1.mat
mecfoc.dat
puertos.txt
tidal.dat
bathy/grid_a.grd
bathy/xa.dat
bathy/ya.dat
ttt_mundo/cortado.i2
```

When command steps are active, the tools directory must contain:

```txt
fault_plane
deform
tsunami
```

## Pipeline

`MASTER_PIPELINE` runs these steps in order:

1. `fault_plane`
2. `deform`
3. `tsunami`
4. `maxola`
5. `ttt_max`
6. `ttt_inverso`
7. `point_ttt`
8. `copy_ttt_svg`
9. `generate_reports`

`run_simulation()` accepts `skip_steps` for technical debugging. Skipped steps
must match names from `MASTER_PIPELINE`.

> [!CAUTION]
> Skipping pipeline steps changes the generated artifacts and can invalidate a
> simulation result. Use `skip_steps` only for local diagnosis and iteration.

## Example

```python
from pathlib import Path

from core import EarthquakeInput
from core.simulation import run_simulation

data = EarthquakeInput(Mw=9.0, h=12.0, lat0=-20.5, lon0=-70.5, hhmm="0000", dia="23")
result = run_simulation(data, Path("jobs/example"))

print(result.calculation)
print(result.travel_times)
print(result.report_path)
```

## Development

From the repository root:

```sh
uv run --package tsdhn-core pytest packages/core/tests
```
