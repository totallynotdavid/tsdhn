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
`COMPUTE_API_URL` with `COMPUTE_API_TOKEN`. The token never reaches the browser,
and no browser code in the web app calls the compute API.

## Repository layout

```text
.github/                  Contributing guide and workflows
apps/web/                 SvelteKit web app
deploy/                   Container images
docs/                     Project manual
libs/api-client/          Generated TypeScript client
model/                    Model inputs and Fortran reference programs
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

### Preview mode

`mise run web:preview` replaces both Postgres and the compute service so the web
app runs on one machine. The web process then holds both sides of the contract
above:

- an in-memory database holds the web tables and `compute.jobs`;
- a compute stub, served by the web process under `/_preview/compute`, stands in
  for the compute API;
- one demo user is signed in.

Two writers own `compute.jobs`, one after the other. The database module creates
the table and seeds the six demo jobs before the server accepts a request. From
the first request on, the stub is the only writer. The rest of the web app only
reads the table.

The stub keeps the rules of [Jobs](jobs.md#states):

- A job moves only forward, `queued` to `running` to `completed` or `failed`. A
  write to a finished job changes nothing.
- A `simulation_id` runs once. Submitting it again with the same input returns
  the existing job and starts no second run. Submitting it with different input
  is rejected with 400.
- The progress stream ends when its job finishes or its client leaves.

### Output storage

The worker uses local disk while a simulation runs. The work directory holds
intermediate files and the checkpoints that recovery needs.

Object storage stores completed output files. The compute database stores their
names, media types, filenames and private object keys. Public API responses omit
the object keys.

## Where the code is

### Engine

| Behavior                                | Code                                        |
| --------------------------------------- | ------------------------------------------- |
| Source parameters and arrival estimates | `packages/tsdhn/tsdhn/calculator.py`        |
| Fault geometry and input files          | `packages/tsdhn/tsdhn/fault_plane.py`       |
| Deformation                             | `packages/tsdhn/tsdhn/deform.py`            |
| Propagation and checkpoints             | `packages/tsdhn/tsdhn/tsunami.py`           |
| Report transformations                  | `packages/tsdhn/tsdhn/render/`              |
| Stage order                             | `packages/tsdhn/tsdhn/pipeline/registry.py` |
| Run setup and output collection         | `packages/tsdhn/tsdhn/engine.py`            |
| Model validation, external tool checks  | `packages/tsdhn/tsdhn/runtime.py`           |
| Versioned model installation            | `packages/tsdhn/tsdhn/assets.py`            |
| Researcher commands                     | `packages/tsdhn/tsdhn/cli/`                 |

### Compute service

| Behavior                               | Code                                    |
| -------------------------------------- | --------------------------------------- |
| Compute routes                         | `packages/api/api/routes.py`            |
| Request and response models            | `packages/api/api/schemas.py`           |
| API token check                        | `packages/api/api/security.py`          |
| Job reads and updates                  | `packages/api/api/core/repository.py`   |
| Queue tasks, workspace lock, retention | `packages/api/api/core/tasks.py`        |
| Shared rqueue instance                 | `packages/api/api/core/queue.py`        |
| Terminal statuses, retention, job ID   | `packages/api/api/core/lifecycle.py`    |
| Start-time check for model data        | `packages/api/api/core/model_assets.py` |
| Worker process                         | `packages/api/api/worker.py`            |
| Compute schema migrations              | `packages/api/api/migrate.py`           |
| Queue roles                            | `packages/api/api/queue_grants.py`      |
| Web role grants                        | `packages/api/api/web_grants.py`        |
| Output uploads and download URLs       | `packages/api/api/core/storage.py`      |

### Web app and client

| Behavior                              | Code                                               |
| ------------------------------------- | -------------------------------------------------- |
| Compute API client for the web server | `apps/web/src/lib/server/compute-api.ts`           |
| Submission and retry                  | `apps/web/src/lib/server/submit-simulation.ts`     |
| Simulation queries                    | `apps/web/src/lib/server/simulation-repository.ts` |
| Join of simulation and compute state  | `apps/web/src/lib/server/simulation-details.ts`    |
| Output name validation                | `apps/web/src/lib/server/outputs.ts`               |
| Generated compute client              | `libs/api-client/`                                 |
| Preview launcher and refusal rules    | `apps/web/scripts/preview.ts`                      |
| Preview database and seed data        | `apps/web/src/lib/server/preview/database.ts`      |
| Preview compute API stub              | `apps/web/src/lib/server/preview/compute-stub.ts`  |
| Preview demo sign-in                  | `apps/web/src/lib/server/preview/hook.ts`          |

### Parity

| Behavior                                | Code                                            |
| --------------------------------------- | ----------------------------------------------- |
| Input-case generation                   | `packages/tsdhn-parity/tsdhn_parity/cases.py`   |
| Checkpoint and trace types              | `packages/tsdhn-parity/tsdhn_parity/trace.py`   |
| Comparisons and tolerances              | `packages/tsdhn-parity/tsdhn_parity/compare.py` |
| Python, Fortran and saved-trace runners | `packages/tsdhn-parity/tsdhn_parity/adapters/`  |
| Cases, readers, tolerances and data     | `packages/tsdhn/tests/parity/<unit>/`           |
