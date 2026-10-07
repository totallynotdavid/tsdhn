# tsdhn-api

`tsdhn-api` accepts requests from the web server, records compute jobs in
PostgreSQL, queues work with `rqueue`, runs the shared `tsdhn` engine, and
stores output files in MinIO. The browser calls the web app, not this service.

See [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) for boundaries and
[`../../docs/deploy.md`](../../docs/deploy.md) for service configuration and
startup.

## Run it

From the repository root, run the API and worker in separate terminals:

```sh
uv run tsdhn-api
uv run tsdhn-worker
```

Apply all local database migrations first:

```sh
mise run db-migrate
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
- `api/migrate.py`: compute schema migration.
- `api/queue_grants.py`: least-privilege queue roles.
- `api/worker.py`: queue worker, workspace sweep, and retention.

## Tests and generated client

Run the fast API tests with:

```sh
uv run --package tsdhn-api pytest packages/api/tests
```

Database-backed tests use:

```sh
mise run test-integration
```

After changing a route or schema, regenerate the TypeScript client:

```sh
mise run gen-client
```
