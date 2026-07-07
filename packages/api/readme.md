# tsdhn-api

`tsdhn-api` serves the TSDHN simulation API. It stores job state in Postgres,
runs long simulations through Procrastinate, writes completed artifacts to
MinIO, and uses the shared `tsdhn` engine.

## Entry Points

```sh
uv run tsdhn-api
uv run tsdhn-worker
uv run tsdhn-compute-migrate
```

`tsdhn-api` starts the FastAPI application from [`api/main.py`](./api/main.py).
`tsdhn-worker` runs a Procrastinate worker from
[`api/worker.py`](./api/worker.py). `tsdhn-compute-migrate` creates the
application-owned `compute_jobs` table; run it after applying the Procrastinate
schema.

The API documentation UI is served at:

```txt
http://localhost:8000/api-docs
```

## Environment

| Variable | Used by | Default | Purpose |
| --- | --- | --- | --- |
| `APP_HOST` | API | `127.0.0.1` | Uvicorn bind host |
| `APP_PORT` | API | `8000` | Uvicorn bind port |
| `ALLOWED_ORIGINS` | API | empty | Comma-separated browser origins for direct CORS access |
| `BACKEND_SERVICE_TOKEN` | API | none | Required bearer token for simulation routes |
| `COMPUTE_DATABASE_URL` | API, worker, migration | `postgresql://tsdhn:tsdhn@localhost:5432/tsdhn_compute` | Worker Postgres connection |
| `PROCRASTINATE_QUEUE` | API, worker | `simulations` | Procrastinate queue name |
| `MINIO_ENDPOINT` | worker, API health | `localhost:9000` | MinIO or S3-compatible endpoint |
| `MINIO_ACCESS_KEY` | worker, API health | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | worker, API health | `minioadmin` | MinIO secret key |
| `MINIO_BUCKET` | worker, API health | `tsdhn-results` | Bucket for artifacts and metadata |
| `MINIO_SECURE` | worker, API health | `false` | Use HTTPS for MinIO client connections |
| `TSDHN_API_LOG` | API | `tsunami_api.log` | API log file path |
| `TSDHN_MODEL_DIR` | API, worker | none | Model asset directory loaded by `tsdhn` |
| `TSDHN_TOOLS_DIR` | worker | none | Directory containing prebuilt model executables |
| `TSDHN_JOBS_DIR` | worker | `jobs` | Temporary per-job simulation workspace root |

The API startup path loads `TsunamiCalculator`, so local API runs need
`TSDHN_MODEL_DIR`. The worker needs both model assets and tool executables for
full simulations.

## Authentication

Health and version routes are unauthenticated:

- `GET /api/v1/health`
- `GET /api/v1/version`

Simulation routes require:

```txt
Authorization: Bearer $BACKEND_SERVICE_TOKEN
```

The SvelteKit app calls these routes server-to-server. Browser code calls the
web app, not FastAPI directly.

## Routes

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health` | No | API liveness, Postgres readiness, and MinIO readiness |
| `GET` | `/api/v1/version` | No | Package name and version |
| `POST` | `/api/v1/calculations` | Yes | Source-parameter and travel-time preview |
| `POST` | `/api/v1/jobs` | Yes | Enqueue a full simulation using the web app's `app_job_id` idempotency key |
| `GET` | `/api/v1/jobs/{app_job_id}` | Yes | Read queue status and completed metadata |
| `GET` | `/api/v1/jobs/{app_job_id}/events` | Yes | Server-sent progress stream |

## Request examples

Health check:

```sh
curl -s http://localhost:8000/api/v1/health
```

Calculation preview:

```sh
curl -s http://localhost:8000/api/v1/calculations \
  -H "Authorization: Bearer $BACKEND_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "Mw": 9.0,
    "h": 12.0,
    "lat0": -20.5,
    "lon0": -70.5,
    "dia": "23",
    "hhmm": "0000"
  }'
```

Enqueue a simulation:

```sh
curl -s http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $BACKEND_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "app_job_id": "4cfe522f-7e7d-46e0-96ca-7b98743fb9f5",
    "input": {
      "Mw": 9.0,
      "h": 12.0,
      "lat0": -20.5,
      "lon0": -70.5,
      "dia": "23",
      "hhmm": "0000"
    }
  }'
```

## Development

From the repository root:

```sh
uv run --package tsdhn-api pytest packages/api/tests
uv run --package tsdhn-api procrastinate --app=api.core.procrastinate_app.app schema --apply
uv run --package tsdhn-api tsdhn-compute-migrate
uv run python scripts/export_openapi.py
```

Regenerate the TypeScript API client after route or schema changes:

```sh
bun run gen:client
```
