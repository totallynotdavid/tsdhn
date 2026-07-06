# tsdhn-api

`tsdhn-api` exposes the TSDHN backend over FastAPI and dispatches long-running
simulations to an RQ worker. The service uses `tsdhn-core` for calculations and
pipeline execution.

## Entry Points

```sh
uv run tsdhn-api
uv run tsdhn-worker
```

`tsdhn-api` starts the FastAPI application from [`api/main.py`](./api/main.py).
`tsdhn-worker` consumes the `tsdhn_queue` RQ queue from
[`api/worker.py`](./api/worker.py).

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
| `REDIS_URL` | API, worker | `redis://localhost:6379/0` | Redis connection for RQ |
| `TSDHN_API_LOG` | API | `tsunami_api.log` | API log file path |
| `TSDHN_MODEL_DIR` | API, worker | none | Model asset directory loaded by `tsdhn-core` |
| `TSDHN_TOOLS_DIR` | worker | none | Directory containing prebuilt model executables |
| `TSDHN_JOBS_DIR` | worker | `jobs` | Per-job simulation workspace root |

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
| `GET` | `/api/v1/health` | No | API liveness and Redis connectivity |
| `GET` | `/api/v1/version` | No | Package name and version |
| `POST` | `/api/v1/calculations` | Yes | Source-parameter and travel-time preview |
| `POST` | `/api/v1/simulations` | Yes | Enqueue a full simulation |
| `GET` | `/api/v1/simulations/{sim_id}` | Yes | Read queue status and completed metadata |
| `GET` | `/api/v1/simulations/{sim_id}/events` | Yes | Server-sent progress stream |
| `GET` | `/api/v1/simulations/{sim_id}/report` | Yes | Download the generated PDF report |

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
curl -s http://localhost:8000/api/v1/simulations \
  -H "Authorization: Bearer $BACKEND_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "Mw": 9.0,
      "h": 12.0,
      "lat0": -20.5,
      "lon0": -70.5,
      "dia": "23",
      "hhmm": "0000"
    },
    "skip_steps": []
  }'
```

## Development

From the repository root:

```sh
uv run --package tsdhn-api pytest packages/api/tests
uv run python scripts/export_openapi.py
```

Regenerate the TypeScript API client after route or schema changes:

```sh
bun run gen:client
```
