# Deploy

The repository includes a Podman Compose stack for the API, the worker,
PostgreSQL, MinIO and the web app. Named volumes hold PostgreSQL data, MinIO
objects and worker workspaces.

## Configure

Copy the example file and fill every blank secret before you start the stack:

```sh
cp .env.example .env
```

Set `COMPUTE_API_TOKEN`, `BETTER_AUTH_SECRET`, `APP_DB_PASSWORD`,
`COMPUTE_PRODUCER_PASSWORD`, `COMPUTE_WORKER_PASSWORD` and
`COMPUTE_PURGER_PASSWORD`. `.env.example` shows the command that generates each
value. The three queue-role passwords belong to the API producer, the worker and
the retention purger. See [Database](database.md#compute-roles).

The example uses queue `simulations` in schema `task_queue` and exposes MinIO at
`localhost:9000` for browser downloads. Set `TSDHN_MINIO_PUBLIC_ENDPOINT` to the
host and port a browser can reach when it differs. Compose sets the runtime
database endpoint and the MinIO endpoint for its containers itself.

### Settings

The API and worker read these environment variables. Defaults apply when a
variable is unset.

| Variable                                                            | Default                                          | Meaning                                                |
| ------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------ |
| `COMPUTE_DATABASE_URL`                                              | `postgresql://tsdhn:tsdhn@localhost:5432/tsdhn`  | Schema-owner URL, used for migrations and provisioning |
| `COMPUTE_RUNTIME_DATABASE_URL`                                      | `COMPUTE_DATABASE_URL`                           | Passwordless URL that runtime roles connect through    |
| `TSDHN_PG_PORT`                                                     | `5432`                                           | Port in the default `COMPUTE_DATABASE_URL`             |
| `COMPUTE_QUEUE`, `COMPUTE_QUEUE_SCHEMA`                             | `simulations`, `task_queue`                      | Queue name and the schema rqueue owns                  |
| `COMPUTE_PRODUCER_ROLE`, `_WORKER_ROLE`, `_PURGER_ROLE`             | `tsdhn_producer`, `tsdhn_worker`, `tsdhn_purger` | Runtime role names                                     |
| `COMPUTE_PRODUCER_PASSWORD`, `_WORKER_PASSWORD`, `_PURGER_PASSWORD` | none (required)                                  | Runtime role passwords                                 |
| `APP_DB_ROLE`, `APP_DB_PASSWORD`                                    | `tsdhn_app`, none                                | Web runtime role                                       |
| `TSDHN_DB_POOL_MIN_SIZE`, `TSDHN_DB_POOL_MAX_SIZE`                  | `0`, `10`                                        | Connection pool bounds                                 |
| `TSDHN_JOBS_DIR`                                                    | `jobs`                                           | Directory that holds one workspace per simulation      |
| `TSDHN_WORKER_CONCURRENCY`                                          | `1`                                              | Simulations a worker runs at once                      |
| `TSDHN_WORKER_LEASE_SECONDS`                                        | `60`                                             | Queue lease length                                     |
| `TSDHN_WORKER_ID`                                                   | empty                                            | Worker name in queue records                           |
| `TSDHN_NUMBA_THREADS`                                               | all visible CPUs                                 | Threads for the solver                                 |
| `TSDHN_LOG_LEVEL`                                                   | `INFO`                                           | Log level                                              |
| `TSDHN_MINIO_ENDPOINT`                                              | `localhost:9000`                                 | MinIO address the API uploads to                       |
| `TSDHN_MINIO_PUBLIC_ENDPOINT`                                       | `TSDHN_MINIO_ENDPOINT`                           | MinIO address in download URLs                         |
| `TSDHN_MINIO_ACCESS_KEY`, `TSDHN_MINIO_SECRET_KEY`                  | `minioadmin`, `minioadmin`                       | MinIO credentials                                      |
| `TSDHN_MINIO_BUCKET`, `TSDHN_MINIO_SECURE`                          | `tsdhn-results`, `false`                         | Bucket name and TLS                                    |
| `TSDHN_OUTPUT_URL_TTL_SECONDS`                                      | `900`                                            | Lifetime of a download URL                             |
| `TSDHN_SSE_MAX_DURATION_SECONDS`                                    | `1800`                                           | Longest progress stream                                |
| `TSDHN_ALLOWED_ORIGINS`                                             | empty                                            | Comma-separated origins that may call the API directly |
| `TSDHN_HOST`, `TSDHN_PORT`                                          | `127.0.0.1`, `8000`                              | Address `tsdhn-api` listens on                         |

Retry limits, the 24 hour workspace lifetime and the seven day queue retention
are fixed in the code. [Jobs](jobs.md) states them.

## Start

Install the pinned tools, then start the base services:

```sh
mise install
mise run dev-up
```

`dev-up` runs `podman compose up -d`. Compose starts PostgreSQL and MinIO, runs
the compute and queue migrations, provisions the runtime roles, and then starts
the API and the worker.

Start the web profile in a second terminal:

```sh
mise run dev-web
```

This applies the web migrations, provisions the web role and runs the web app in
the foreground. Open <http://localhost:3000>.

| Address                          | Service                 |
| -------------------------------- | ----------------------- |
| <http://localhost:3000>          | Web app                 |
| <http://localhost:8000/api-docs> | Compute API, OpenAPI UI |
| <http://localhost:9001>          | MinIO console           |

The compute API serves its routes under `/api/v1`. The health and version routes
are public. The other routes need `COMPUTE_API_TOKEN`.

## Inspect and stop

Follow the service logs:

```sh
mise run dev-logs
```

Stop the containers and keep the named volumes:

```sh
mise run dev-down
```

To delete PostgreSQL data, MinIO objects and worker workspaces as well, run
`podman compose down -v`.

## Run without Compose

The API and worker can run on the host against the PostgreSQL cluster that mise
manages. They need the model data, which `tsdhn assets install` downloads, and
they need MinIO, which Compose can provide:

```sh
uv run tsdhn assets install
podman compose up -d minio
```

Without MinIO the API starts and `/api/v1/health` reports
`"storage_connected": false`.

Apply every migration in order. The task starts PostgreSQL, migrates the compute
schema and the queue, provisions the queue roles, migrates the web schema and
provisions the web role:

```sh
mise run db-migrate
```

Run the API and the worker in separate terminals:

```sh
mise run api
mise run worker
```

`db-migrate`, `api` and `worker` read `.env`, so the passwords and token you set
for Compose apply here too. The API uses the producer role, the worker uses the
worker role, and retention uses the purger role.

Both processes exit at start with the missing paths when the model assets are
not installed. Run `uv run tsdhn assets install`, or point `TSDHN_MODEL_DIR` at
the repository's `model/` directory. `scripts/setup.sh` records that variable in
`.tsdhn/env`, which mise loads.
