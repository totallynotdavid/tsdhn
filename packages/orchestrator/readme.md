# orchestrator

TSDHN tsunami simulation orchestrator.

FastAPI service that exposes the simulation API and dispatches jobs to an
RQ worker. See the workspace root [README](../../README.md) for full setup
instructions.

## Entry point

```sh
uv run tsdhn-api        # starts the FastAPI app via uvicorn
uv run rq worker tsdhn_queue   # starts the RQ worker
```

## Development

```sh
uv run --package orchestrator pytest
```
