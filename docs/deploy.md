# Deploy

The repository includes a Docker Compose stack for the API, the worker,
PostgreSQL, RustFS and the web app. Compose runs over the Podman socket. Named
volumes hold PostgreSQL data, object storage data and worker workspaces.

The stack pins RustFS `docker.io/rustfs/rustfs:1.0.1`.

## Configure

Create the local environment before you start the stack (also done by `dev`):

```sh
mise run env-init
```

`env-init` refuses to overwrite an existing `.env`, generates the six required
secrets and writes the file with mode 600. The three queue-role passwords belong
to the API producer, the worker and the retention purger. See
[Database](database.md#compute-roles).

The example uses queue `simulations` in schema `task_queue` and exposes RustFS
at `localhost:9000` for browser downloads. Set `TSDHN_S3_PUBLIC_ENDPOINT` to the
host and port a browser can reach when it differs. Compose sets the runtime
database endpoint and the internal S3 endpoint for its containers itself.

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
| `TSDHN_S3_ENDPOINT`                                                 | `localhost:9000`                                 | S3 address the API uploads to                          |
| `TSDHN_S3_PUBLIC_ENDPOINT`                                          | `TSDHN_S3_ENDPOINT`                              | S3 address in download URLs                            |
| `TSDHN_S3_ACCESS_KEY`, `TSDHN_S3_SECRET_KEY`                        | `tsdhn-local`, `tsdhn-local-secret`              | S3 credentials                                         |
| `TSDHN_S3_BUCKET`, `TSDHN_S3_SECURE`                                | `tsdhn-results`, `false`                         | Bucket name and TLS                                    |
| `TSDHN_OUTPUT_URL_TTL_SECONDS`                                      | `900`                                            | Lifetime of a download URL                             |
| `TSDHN_SSE_MAX_DURATION_SECONDS`                                    | `1800`                                           | Longest progress stream                                |
| `TSDHN_ALLOWED_ORIGINS`                                             | empty                                            | Comma-separated origins that may call the API directly |
| `TSDHN_HOST`, `TSDHN_PORT`                                          | `127.0.0.1`, `8000`                              | Address `tsdhn-api` listens on                         |

Retry limits, the 24 hour workspace lifetime and the seven day queue retention
are fixed in the code. [Jobs](jobs.md) states them.

## Start

Install the pinned tools, then start the complete local stack:

```sh
mise install
mise run dev
```

`dev` creates `.env` when it is missing, checks the Podman socket, builds local
images, starts every service in detached mode, applies migrations and waits for
the API and web health checks. It prints the addresses when they are ready. Open
`/signup` to create a local account with an email and a password of at least 8
characters. Local accounts do not need email verification.

| Address                          | Service                 |
| -------------------------------- | ----------------------- |
| <http://localhost:3000>          | Web app                 |
| <http://localhost:8000/api-docs> | Compute API, OpenAPI UI |
| <http://localhost:9001>          | RustFS storage console  |

The compute API serves its routes under `/api/v1`. The health and version routes
are public. The other routes need `COMPUTE_API_TOKEN`.

## Inspect and stop

Follow the service logs:

```sh
mise run dev-logs
```

Show each container's state and configured health status:

```sh
mise run dev-status
```

Stop the containers and keep the named volumes:

```sh
mise run dev-down
```

`dev-down` keeps the named volumes. The database and storage are disposable, so
wipe the containers, network and volumes when resetting the stack. The command
uses the same engine socket setup as the mise tasks:

```sh
. scripts/dev-engine.sh && docker compose --profile web down -v
```
