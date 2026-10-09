# TSDHN

TSDHN simulates tsunamis from earthquake source parameters. Researchers use it
to estimate source dimensions, port arrival times and wave propagation across
the Pacific Ocean from the command line or a web app. The model grid covers the
Pacific from 76°S to 61°N, and the 17 report ports are on the coast of Peru and
at Arica.

```sh
uv run tsdhn calc --mw 8.0 --lat -20.5 --lon -70.5
```

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

`calc` is an estimate that needs no services. `tsdhn run` runs the full
pipeline: fault plane, seafloor deformation, wave propagation and the report
maps. The web app and compute API run the same pipeline for many users.

## Install

Install the pinned tools and start the local stack:

```sh
mise install && mise run dev
```

`mise run env-init` creates `.env` from `.env.example` with generated secrets.
`mise run dev` runs it automatically when `.env` is missing. It refuses to
overwrite an existing file.

For the command-line model, download the model data and check the toolchain:

```sh
mise run install
uv run tsdhn assets install
uv run tsdhn doctor
```

`tsdhn run` also needs GMT (6.5.0 or newer) and `ttt_client` on `PATH`.
`tsdhn doctor` reports which of them are missing. `calc` needs neither. On an
apt-based system, `scripts/setup.sh` installs both with `sudo`. It prints its
plan and asks before it changes anything. It also installs Intel Fortran and
compiles the parity tools unless you pass `--skip-ifx` or `--skip-tools`.
`--help` lists every option.

Run the full pipeline with the same inputs:

```sh
uv run tsdhn run --mw 8.0 --lat -20.5 --lon -70.5
```

The run directory defaults to `jobs/<timestamp>`. Install the web app
dependencies with `mise run web-install`, and start the services as described in
[Deploy](docs/deploy.md).

## Features

- The Python engine calculates source parameters, propagates the tsunami and
  writes fixed-format maps, station reports and checkpoints.
- The CLI installs versioned model data, checks external tools, previews a
  calculation and runs the pipeline.
- The compute API queues simulations. The worker resumes interrupted work and
  stores finished files in S3-compatible object storage.
- The web app signs researchers in, tracks their simulations, streams progress
  and creates output downloads.
- The parity package compares selected Python results with saved MATLAB and
  Fortran results.

## Learn more

- [Manual](docs/readme.md): architecture, operations, pipeline and tests.
- [Contributing](.github/contributing.md): set up, check and change the code.
