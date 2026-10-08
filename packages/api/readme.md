# tsdhn-api

`tsdhn-api` accepts requests from the web server, records compute jobs in
PostgreSQL, queues work with `rqueue`, runs the shared `tsdhn` engine, and
stores output files in MinIO. The browser calls the web app, not this service.

[Architecture](../../docs/architecture.md) states the boundaries,
[Jobs](../../docs/jobs.md) the job rules, and [Deploy](../../docs/deploy.md) the
configuration and startup.

## Run it

From the repository root, apply all local database migrations, then run the API
and the worker in separate terminals. What they need before they start is in
[Deploy](../../docs/deploy.md#run-without-compose).

```sh
mise run db-migrate
mise run api
mise run worker
```

The compute API's OpenAPI UI is at <http://127.0.0.1:8000/api-docs>. Health and
version routes are public. Simulation and calculation routes require
`COMPUTE_API_TOKEN`.

## Package map

- `api/routes.py`: health, calculation, submission, progress, and output routes.
- `api/schemas.py`: public request and response models.
- `api/security.py`: API token checks.
- `api/core/repository.py`: compute-job reads and updates.
- `api/core/tasks.py`: queued simulation task.
- `api/core/storage.py`: output uploads and download URLs.
- `api/core/queue.py`: shared rqueue instance.
- `api/migrate.py`: applies the numbered files in `api/migrations/`.
- `api/core/lifecycle.py`: retention, terminal statuses, and the job id pattern.
- `api/core/model_assets.py`: start-time check for the installed model data.
- `api/queue_grants.py`: least-privilege queue roles.
- `api/web_grants.py`: web role grants.
- `api/worker.py`: queue worker, workspace sweep, and retention.

## Tests

Run the fast API tests with:

```sh
uv run --package tsdhn-api pytest packages/api/tests -m "not integration"
```

Database-backed tests use `mise run test-integration`. After a route or schema
change, regenerate the TypeScript client as described in
[`libs/api-client`](../../libs/api-client/readme.md#regenerate).
