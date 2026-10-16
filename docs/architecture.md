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
Edge route (see [Deploy](deploy.md#cloudflare-edge-route))
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

Production has two host roles. The main host runs the web app, the compute API,
PostgreSQL, the backup and the tunnel, and it runs a worker. A worker host runs
only a worker. It reaches PostgreSQL over a private network and uploads outputs
to object storage, so it needs nothing else from the main host. Any number of
worker hosts can join. [Deploy](deploy.md#add-a-worker-host) describes the
setup.

The browser talks to the web app. The web app checks the session and handles the
researcher-facing flow. Its server code calls the compute API at
`COMPUTE_API_URL` with `COMPUTE_API_TOKEN`. The token never reaches the browser,
and no browser code in the web app calls the compute API.

## Repository layout

```text
.github/                  Contributing guide and workflows
apps/web/                 SvelteKit web app
deploy/                   Container images, edge Worker and production Compose files
docs/                     Project manual
libs/api-client/          Generated TypeScript client
model/                    Model inputs and Fortran reference programs
packages/tsdhn/           Simulation engine and researcher CLI
packages/api/             FastAPI service and worker
packages/tsdhn-parity/    Comparison with MATLAB and Fortran output
scripts/                  Setup, generation, database, and end-to-end tasks
docker-compose.yml        Local service stack
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

### Shared state across hosts

Several workers on several hosts act on the same state. Each row below names the
state, who may move it and when. [Jobs](jobs.md#invariants) holds the transition
rules of the compute row.

| State                                          | Moved by                                                     | When                                                                                                                                    |
| ---------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| Queue task: `pending`                          | API (enqueue); the queue (lease expired)                     | A job is submitted or retried, or a lease ran out with attempts left.                                                                   |
| Queue task: `leased`                           | A worker on any host                                         | It claims a `pending` task and renews the lease every beat. One worker holds a lease.                                                   |
| Queue task: `succeeded`, `failed`, `cancelled` | The worker that holds the lease; the queue                   | The lease fence accepts the attempt. A worker whose attempt lost the job cancels it. The queue fails a task whose last attempt expired. |
| Queue task row deleted                         | The purger, on the main host only                            | The task is terminal for seven days and its compute job is finished.                                                                    |
| `compute.jobs` row                             | The worker that holds the lease; any worker's reconciliation | `owner_attempt` fences it. A superseded attempt cannot write.                                                                           |
| Output objects                                 | The worker that ran the job                                  | It uploads before it marks the job `completed`. Output expiry, on the main host only, deletes them.                                     |
| Workspace and checkpoints (`jobs-data` volume) | The worker on that host                                      | Under the workspace lock. No other host reads it, so a job that moves starts over.                                                      |

Retention is one task for the whole deployment, not one per host: the main
host's worker runs the queue purge and the output expiry, and a worker host sets
`TSDHN_RETENTION_ENABLED=false`. Every worker reconciles the jobs the queue gave
up on.

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
intermediate files and the checkpoints that recovery needs. Checkpoints stay on
the host that wrote them, so a job that moves to another host starts over.

Object storage stores completed output files. It is S3-compatible: Cloudflare R2
in production, or the bundled RustFS. Every worker uploads to it directly, and
the API signs the download URLs against the same endpoint. The compute database
stores their names, media types, filenames and private object keys. Public API
responses omit the object keys. The main host deletes a job's files after the
output retention ([Jobs](jobs.md#output-retention)); worker hosts run no
retention pass.

The production stack copies the database and the stored outputs off the host
every day. The work directory is not copied, so a restored stack has none of the
checkpoints of a job that was still running.
[Deploy](deploy.md#backup-and-restore) describes the backup.

### Health signals

Each long-running service tells its supervisor whether it can work. The
supervisor only reads these signals. [Deploy](deploy.md#health-checks) lists
which check reads which.

| Service | Signal               | Healthy                           | Unhealthy                                      |
| ------- | -------------------- | --------------------------------- | ---------------------------------------------- |
| API     | `GET /api/v1/health` | 200, database and storage answer  | 503, the body names the dependency that failed |
| Web     | `GET /health`        | 200, the database answers         | 503                                            |
| Worker  | heartbeat file mtime | Fresh: touched less than 60 s ago | Absent or stale                                |
| Backup  | last-backup file     | Touched less than two intervals   | Absent or stale                                |

The API body also carries `oldest_queued_age_seconds`, the wait of the job that
has been claimable longest, `0.0` when none waits. It is a load signal for
[adding a worker host](deploy.md#add-a-worker-host) and never changes the
status.

The worker owns its heartbeat file, named by `TSDHN_WORKER_HEARTBEAT_FILE`. Its
states:

- **Absent**: the worker has not completed a beat since the container's file
  system was created. This is the state at the start of a new container.
- **Fresh**: the last beat ran less than 60 seconds ago. A beat runs every 10
  seconds and touches the file only after `SELECT 1` on the worker's database
  pool succeeds, so a fresh file means the worker's event loop runs and the
  database answers.
- **Stale**: the last beat is 60 seconds old or more. The event loop is blocked,
  the database is unreachable, or the process has died. A container restart
  leaves the previous file in place, and it is stale until the first beat of the
  new process.

Only the worker process creates or touches the file, and nothing deletes it. The
60-second limit belongs to the reader, the health check in
`deploy/compose.prod.yml`, so the worker never decides that it is unhealthy. A
worker started without `TSDHN_WORKER_HEARTBEAT_FILE` writes no file.

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
