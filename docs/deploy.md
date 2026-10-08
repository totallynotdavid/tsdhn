# Deploy the local stack

The repository includes a Podman Compose stack for the API, worker, PostgreSQL,
MinIO, and the optional web app. The stack uses named volumes for PostgreSQL,
MinIO, and worker workspaces.

## Configure

Copy the example file and fill every blank secret before starting the stack:

```sh
cp .env.example .env
```

Set `COMPUTE_API_TOKEN`, `BETTER_AUTH_SECRET`, `APP_DB_PASSWORD`,
`COMPUTE_PRODUCER_PASSWORD`, `COMPUTE_WORKER_PASSWORD`, and
`COMPUTE_PURGER_PASSWORD`. Generate secret values with the commands shown in
`.env.example`. The three queue-role passwords belong to the API producer,
worker, and retention purger respectively.

The example configures queue `simulations` in schema `task_queue`, uses
PostgreSQL on the Compose service name, and exposes MinIO at `localhost:9000`
for browser downloads. Set `TSDHN_MINIO_PUBLIC_ENDPOINT` to the host and port a
browser can reach when that is different. Compose sets the runtime database
endpoint and the MinIO endpoint for the containers itself.

## Start

Install the pinned tools, then start the base services:

```sh
mise install
mise run dev-up
```

`dev-up` runs `podman compose up -d`. Compose starts PostgreSQL and MinIO, runs
the compute and queue migrations, provisions the runtime roles, and then starts
the API and worker.

Start the web profile in a second terminal:

```sh
mise run dev-web
```

This applies the web migrations, provisions the web role, and starts the web app
in the foreground. Visit <http://localhost:3000>. The compute API's OpenAPI UI
is at <http://localhost:8000/api-docs>.

## Inspect and stop

Follow service logs while the stack is running:

```sh
mise run dev-logs
```

Stop the containers and keep named volumes:

```sh
mise run dev-down
```

PostgreSQL, MinIO objects, and worker workspaces remain in their named volumes.
Remove them through the Podman Compose volume command only when the stored data
is no longer needed.

## Run without Compose

For a local development database, use the mise-managed PostgreSQL cluster and
apply all migrations in order:

```sh
mise run db-migrate
```

The task starts PostgreSQL, runs the compute migration, runs the rqueue
migration, provisions queue roles, runs web migrations, and provisions the web
role. The API and worker can then run from separate terminals:

```sh
mise run api
mise run worker
```

`mise run api`, `mise run worker`, and `mise run db-migrate` read `.env`, so the
passwords and token you set for Compose apply here too. The API uses the
producer role, the worker uses the worker role, and retention uses the purger
role.

Both processes stop at start with the missing paths when the model assets are
not installed. Run `uv run tsdhn assets install`, or point `TSDHN_MODEL_DIR` at
the repository's `model/` directory. `scripts/setup.sh` records that variable in
`.tsdhn/env`, which mise loads.
