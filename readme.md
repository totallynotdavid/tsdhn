# TSDHN

TSDHN runs tsunami simulations from earthquake source parameters. It provides a
Python engine and researcher CLI, a FastAPI compute service and worker, and a
SvelteKit web app for submitting simulations and downloading their outputs.

## Install

Install the pinned tools and project dependencies:

```sh
mise install
mise run install
mise run web-install
```

Install the model dataset and inspect the local toolchain:

```sh
uv run tsdhn assets install
uv run tsdhn doctor
```

## Calculate

Calculate source parameters and approximate arrival times without starting the
services:

```sh
uv run tsdhn calc --mw 8.0 --lat -20.5 --lon -70.5
```

The command prints the calculated source parameters and arrival-time table:

```text
                 Source parameters
┌──────────────────────┬───────────────────────────┐
│ Rupture length (km)  │ 162.18                    │
│ Rupture width (km)   │ 70.79                     │
│ Dislocation (m)      │ 2.741                     │
│ Seismic moment (N.m) │ 1.259e+21                 │
│ Azimuth (deg)        │ 358.0                     │
│ Dip (deg)            │ 14.0                      │
│ Coast distance (km)  │ 115.5                     │
│ Epicenter location   │ mar                       │
│ Tsunami warning      │ Genera un Tsunami pequeno │
└──────────────────────┴───────────────────────────┘
           Tsunami arrival times
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Port       ┃ Arrival     ┃ Distance (km) ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ La Cruz    │ 02:56 23Oct │        2170.3 │
│ Talara     │ 02:53 23Oct │        2120.1 │
│ Paita      │ 02:48 23Oct │        2062.0 │
│ Pimentel   │ 02:30 23Oct │        1828.1 │
│ Salaverry  │ 02:16 23Oct │        1641.0 │
│ Chimbote   │ 02:08 23Oct │        1539.8 │
│ Huarmey    │ 01:59 23Oct │        1420.4 │
│ Huacho     │ 01:50 23Oct │        1290.5 │
│ Callao     │ 01:41 23Oct │        1176.4 │
│ Cerro Azul │ 01:31 23Oct │        1046.6 │
│ Pisco      │ 01:25 23Oct │         965.4 │
│ San Juan   │ 01:09 23Oct │         755.0 │
│ Atico      │ 00:49 23Oct │         582.1 │
│ Camana     │ 00:41 23Oct │         485.0 │
│ Matarani   │ 00:36 23Oct │         424.3 │
│ Ilo        │ 00:28 23Oct │         329.8 │
│ Arica      │ 00:19 23Oct │         225.8 │
└────────────┴─────────────┴───────────────┘
```

Run the full local pipeline with the same inputs:

```sh
uv run tsdhn run --mw 8.0 --lat -20.5 --lon -70.5
```

## Features

- The Python engine calculates source parameters, propagates the tsunami, and
  writes fixed-format maps, station reports, and checkpoints.
- The CLI installs versioned model data, checks external capabilities, previews
  a calculation, and runs the pipeline.
- The compute API queues simulations, and the worker resumes interrupted work
  and stores completed files in MinIO.
- The web app authenticates researchers, tracks simulations, streams progress,
  and creates output downloads.
- The parity package compares selected Python results with saved MATLAB and
  Fortran results.

Read the [manual](./docs/readme.md) for operations, architecture, and testing.
See [CONTRIBUTING.md](./CONTRIBUTING.md) for the contributor workflow.
