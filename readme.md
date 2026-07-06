# TSDHN orchestrator

<!-- prettier-ignore-start -->
<div align="center">

[![CI](https://github.com/totallynotdavid/picv-2025/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/totallynotdavid/picv-2025/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/totallynotdavid/fb9b3bc6236ef7e8a1560403b5c58186/raw/e20fcb208809dbdea85b08d019923225699c2187/covbadge.json)](https://github.com/totallynotdavid/picv-2025/actions/workflows/ci.yml)
[![Security](https://github.com/totallynotdavid/picv-2025/actions/workflows/security.yml/badge.svg)](https://github.com/totallynotdavid/picv-2025/actions/workflows/security.yml)
[![OpenSSF Scorecard](https://img.shields.io/ossf-scorecard/github.com/totallynotdavid/picv-2025?label=scorecard)](https://scorecard.dev/viewer/?uri=github.com/totallynotdavid/picv-2025)

</div>
<!-- prettier-ignore-end -->

TSDHN orchestrator runs tsunami simulation workflows from earthquake source
parameters. The repository contains the shared numerical core, a FastAPI
backend, an RQ worker, a CLI for researchers, a SvelteKit web app, and the generated
TypeScript API client used by the web server.

## Documentation

| Area | Docs | Covers |
| --- | --- | --- |
| Python core | [`packages/core`](./packages/core/readme.md) | Calculations, runtime paths, pipeline execution |
| API service | [`packages/api`](./packages/api/readme.md) | FastAPI routes, service-token auth, worker entry point |
| CLI | [`packages/cli`](./packages/cli/readme.md) | Local `tsdhn` commands for calculation previews and full simulations |
| Web app | [`apps/web`](./apps/web/readme.md) | SvelteKit app, auth, database, and server-side backend configuration |
| API client | [`libs/api-client`](./libs/api-client/readme.md) | OpenAPI schema and generated TypeScript types |

> [!TIP]
> Start with the component README for the package or app you are changing. The root
> README gives orientation and shared commands; component READMEs carry the
> exact usage details for their own layer.

## Architecture

```mermaid
flowchart LR
    Browser[Browser] --> Web[SvelteKit web app]
    Web -->|server-side Bearer token| API[FastAPI /api/v1]
    API -->|enqueue job| Redis[(Redis / RQ)]
    Worker[RQ worker] -->|consume tsdhn_queue| Redis
    Worker --> Core[tsdhn-core]
    CLI[tsdhn CLI] --> Core
    Core --> Model[model assets]
    Core --> Tools[Fortran, GMT, TTT, Typst]
    Worker --> Jobs[(jobs directory)]
    Web --> DB[(SQLite/libSQL)]
```

The browser talks to the SvelteKit app. The SvelteKit server calls the FastAPI
backend with `BACKEND_SERVICE_TOKEN`; that token is never sent to browser code.
Long simulations run in the RQ worker, which calls `tsdhn-core` and writes job
artifacts under `TSDHN_JOBS_DIR`.

## Quick start

The backend stack is self-hosted because the simulation runtime needs the
Fortran/GMT/TTT/Typst toolchain. Docker Compose uses the images and Dockerfiles
under [`deploy/`](./deploy/).

```sh
cp .env.example .env
docker compose up -d
```

Set `BACKEND_SERVICE_TOKEN` and `BETTER_AUTH_SECRET` in `.env` before running
the web profile:

```sh
docker compose --profile web up
```

For local development, install the pinned tools with
[mise](https://mise.jdx.dev/getting-started.html), then install the Python
workspace:

```sh
mise install
mise run install
mise run test
```

The repository uses [uv](https://docs.astral.sh/uv/) for Python packages and
[Bun](https://bun.sh/docs) for the web workspace. Windows users run the
scientific backend under WSL 2; Microsoft documents the setup in the
[WSL install guide](https://learn.microsoft.com/windows/wsl/install).

## Common commands

| Command | Purpose |
| --- | --- |
| `mise run install` | Install all Python workspace packages with dev and build groups |
| `mise run test` | Run the Python test suite with `pytest -n auto` |
| `mise run lint` | Run Ruff and mypy for Python packages |
| `mise run api` | Start the FastAPI service with `tsdhn-api` |
| `mise run worker` | Start the RQ worker with `tsdhn-worker` |
| `mise run web-dev` | Start the SvelteKit dev server |
| `mise run gen-client` | Export FastAPI OpenAPI JSON and regenerate TypeScript types |
| `docker compose up -d` | Run Redis, libSQL, API, and worker |
| `docker compose --profile web up` | Run the backend stack plus the SvelteKit web app |

## Workspace

```txt
picv-2025/
├── apps/
│   └── web/                  # SvelteKit app and server-side web routes
├── deploy/                   # Dockerfiles for toolchain, API, and web images
├── libs/
│   └── api-client/           # Generated TypeScript client from FastAPI OpenAPI
├── model/                    # TSDHN model assets and legacy Fortran sources
├── packages/
│   ├── api/                  # FastAPI service and RQ worker
│   ├── cli/                  # Typer/Rich CLI for researchers
│   └── core/                 # Shared numerical core and simulation pipeline
├── scripts/
│   ├── export_openapi.py     # FastAPI schema export
│   └── gen-client.ts         # OpenAPI TypeScript generation
├── docker-compose.yml
├── mise.toml                 # Tool versions and repo tasks
├── package.json              # Bun workspaces for apps/* and libs/*
├── pyproject.toml            # uv workspace for packages/*
└── uv.lock
```

## Runtime notes

`tsdhn-core` validates model and tool paths before running simulations.
Non-container backend runs need:

- `TSDHN_MODEL_DIR` pointing at the model asset directory.
- `TSDHN_TOOLS_DIR` pointing at prebuilt `fault_plane`, `deform`, and `tsunami`
  executables when command pipeline steps are active.
- `TSDHN_JOBS_DIR` for queued simulation workspaces when running the API worker.

The Docker API image sets these paths to `/app/model`, `/app/tools`, and
`/app/jobs`.

<details>
<summary>Scientific runtime dependencies for non-container backend runs</summary>

The containerized path is the maintained setup for the backend runtime.
Non-container runs must provide the same external tools:

- Intel Fortran compiler (`ifx`) from
  [Intel oneAPI Fortran Essentials](https://www.intel.com/content/www/us/en/docs/oneapi/installation-guide-linux/latest/overview.html)
- [Generic Mapping Tools](https://docs.generic-mapping-tools.org/latest/)
- [TTT SDK](https://www.geoware-online.com/tsunami.html), including
  `ttt_client`
- [Typst](https://typst.app/docs/)
- Redis, `ps2eps`, and `csh`

</details>

## License

This project is licensed under the terms declared in
[`pyproject.toml`](./pyproject.toml).
