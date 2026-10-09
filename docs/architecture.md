# Architecture

This page says what each component owns and where its code lives. For how a
simulation moves between them, read [Jobs](jobs.md). For the tables and roles,
read [Database](database.md). For running the services, read
[Deploy](deploy.md).

## System

```text
Browser
  |
  v
SvelteKit web app
  |-- users, sessions, and simulations in public
  |-- reads current jobs from compute.jobs
  |
  v
FastAPI compute service
  |-- compute.jobs and the rqueue task_queue schema
  |-- worker -> tsdhn engine -> object storage
```

The browser talks to the web app. The web app checks the session and handles the
researcher-facing flow. Its server code calls the compute API at
`COMPUTE_API_URL` with `COMPUTE_API_TOKEN`. The browser never receives the token
and never calls the compute API directly.

## Repository layout

```text
apps/web/                 SvelteKit web app
deploy/                   Container images
docs/                     Project manual
libs/api-client/          Generated TypeScript client
model/                    Model inputs and older reference programs
packages/tsdhn/           Simulation engine and researcher CLI
packages/api/             FastAPI service and worker
packages/tsdhn-parity/    Comparison with MATLAB and Fortran output
scripts/                  Setup, generation, database, and end-to-end tasks
docker-compose.yml        Self-hosted service stack
mise.toml                 Project tasks
```

## Responsibilities

### Web app

The web app owns:

- users, sessions, accounts, and verification records;
- `simulation_id`, user ID, submitted parameters, and creation time;
- failures that happen while submitting a simulation to the compute service;
- authentication, ownership checks, and user-facing responses;
- joining the simulation with current compute state for display.

It does not store compute progress, queue state, the internal compute job ID, or
output storage keys.

### Compute service

The compute service owns:

- the API used by the web server;
- `compute.jobs` and the `task_queue` schema that rqueue owns;
- the internal compute job ID;
- job progress, retry state and worker heartbeats;
- simulation work directories and checkpoints;
- output metadata and uploads to object storage.

It receives a `simulation_id` from the web app. It knows nothing about web
sessions, users or passwords.

### Simulation engine

The `tsdhn` package owns the scientific calculation, the pipeline order, the run
directory, checkpoints and output files. It does not depend on web users,
PostgreSQL jobs, queues or object storage. [Pipeline](pipeline.md) describes its
stages. [Science](science.md) records its numerical rules.

### Output storage

The worker uses local disk while a simulation runs. The work directory holds
intermediate files and the checkpoints that recovery needs.

Object storage stores completed output files. The compute database stores their
names, media types, filenames and private object keys. Public API responses omit
the object keys.

## Where the code is

| Behavior                                | Code                                        |
| --------------------------------------- | ------------------------------------------- |
| Source parameters and arrival estimates | `packages/tsdhn/tsdhn/calculator.py`        |
| Fault geometry and input files          | `packages/tsdhn/tsdhn/fault_plane.py`       |
| Deformation                             | `packages/tsdhn/tsdhn/deform.py`            |
| Propagation and checkpoints             | `packages/tsdhn/tsdhn/tsunami.py`           |
| Report transformations                  | `packages/tsdhn/tsdhn/render/`              |
| Stage order                             | `packages/tsdhn/tsdhn/pipeline/registry.py` |
| Run setup and output collection         | `packages/tsdhn/tsdhn/engine.py`            |
| Compute routes                          | `packages/api/api/routes.py`                |
| Job reads and updates                   | `packages/api/api/core/repository.py`       |
| Queue tasks, workspace lock, retention  | `packages/api/api/core/tasks.py`            |
| Worker process                          | `packages/api/api/worker.py`                |
| Queue roles                             | `packages/api/api/queue_grants.py`          |
| Output uploads and download URLs        | `packages/api/api/core/storage.py`          |
| Web server code                         | `apps/web/src/lib/server/`                  |
| Generated compute client                | `libs/api-client/`                          |
