# tsdhn-api

`tsdhn-api` accepts requests from the web server, records compute jobs in
PostgreSQL, queues work with `rqueue`, runs the shared `tsdhn` engine, and
stores output files in S3-compatible object storage. The browser calls the web
app, not this service.

[Architecture](../../docs/architecture.md) states the boundaries,
[Jobs](../../docs/jobs.md) the job rules, and [Deploy](../../docs/deploy.md) the
configuration and startup.

## Run it

From the repository root, `mise run dev` starts PostgreSQL, object storage, the
migrations, this API, the worker and the web app as containers.
[Deploy](../../docs/deploy.md#start) states the first-run steps.

The compute API's OpenAPI UI is at <http://127.0.0.1:8000/api-docs>. Health and
version routes are public. Simulation and calculation routes require
`COMPUTE_API_TOKEN`.

[Architecture](../../docs/architecture.md#where-the-code-is) lists where each
module lives. `api/migrate.py` applies the numbered files in `api/migrations/`.

## Tests

Run the fast API tests with:

```sh
uv run --package tsdhn-api pytest packages/api/tests -m "not integration"
```

Database-backed tests use `mise run test-integration`. After a route or schema
change, regenerate the TypeScript client as described in
[`libs/api-client`](../../libs/api-client/readme.md#regenerate).
