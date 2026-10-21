tsdhn 0.2.0 is out.

Three months after v0.0.1, this release splits web and compute job state, moves
the compute service to a new queue and to S3-compatible storage, and rebuilds
the web app. It is a breaking release for anyone running the stack: the
environment file and the database are rebuilt, not migrated.

The biggest change is where job state lives. The web app now owns only the
submission: it creates the public `simulation_id`, keeps its own row and handles
retries. The compute service owns `compute.jobs` and the queue, keyed by that
ID, so a repeated submission with the same input returns the existing job
instead of starting a second simulation. The internal job ID and the output
object keys no longer leave the compute service.

The queue backend changed from Procrastinate to rqueue. Leases, retries and
crash recovery are explicit, and the runtime processes connect through three
least-privilege roles: producer, worker and purger. The schema is applied as
numbered files by `tsdhn-compute-migrate`, and web and compute read the same job
lifecycle definition.

Output files moved to S3-compatible storage. The compose stacks bundle RustFS;
an external bucket such as Cloudflare R2 works too. The web app streams
downloads through its own server, so neither the API nor the bucket needs a
public address. Completed jobs keep their files for
`TSDHN_OUTPUT_RETENTION_DAYS` (90 by default), then a purger deletes them; the
simulation page says when the files expired.

The web app was rebuilt on SvelteKit 3 with a new design system. The simulation
form now rejects epicenters outside the model's Pacific domain instead of
letting the compute service extrapolate them. A preview mode runs the whole app
against an embedded database and a compute stub with no services. New since
v0.0.1: a `/health` route and streamed output downloads.

Operations got a production compose stack, encrypted off-host backups with a
restore drill, a way to add more worker hosts, and an optional Cloudflare Worker
at the edge. The worker writes a heartbeat file, and the API's health route
returns 503 when a dependency is down and reports the age of the oldest queued
job.

On the engine side, focal-mechanism selection is centralized and writes four xyo
fields, shared physical constants live in one place, and a malformed gauge
checkpoint is treated as unusable so the run restarts at step zero. Station data
moved to a shared `tsdhn.data` package, and the CLI takes `--verbose` and reads
`TSDHN_LOG_LEVEL`. The rest is tests, documentation and dependency updates.

## Breaking changes

**Environment variables were renamed.** API and worker settings now use the
`TSDHN_` prefix, queue and database-role settings use `COMPUTE_`, and the MinIO
settings became S3 settings. Regenerate the file instead of editing it in place:

```sh
# v0.0.1
APP_HOST=0.0.0.0
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=...

# v0.2.0
TSDHN_HOST=0.0.0.0
TSDHN_S3_ENDPOINT=storage:9000
TSDHN_S3_ACCESS_KEY=...
```

Three variables are new and have no default: `COMPUTE_PRODUCER_PASSWORD`,
`COMPUTE_WORKER_PASSWORD` and `COMPUTE_PURGER_PASSWORD`.

**The database schema has no upgrade path.** `compute.jobs` and the `task_queue`
schema replace the v0.0.1 tables, including the Procrastinate queue tables. The
numbered migrations create the schema from scratch; they do not convert an
existing database. Recreate it: `mise run db:reset` for the local stack, or a
fresh PostgreSQL volume in production.

**Object storage is required.** The worker uploads results to an S3-compatible
bucket instead of writing them to local storage. The compose stacks include
RustFS, so a fresh deploy needs nothing extra. A deployment with its own store
sets `TSDHN_S3_ENDPOINT`, `TSDHN_S3_ACCESS_KEY`, `TSDHN_S3_SECRET_KEY` and
`TSDHN_S3_BUCKET`.

## Known problems

None known.

## Upgrade

Python package: `uv pip install tsdhn==0.2.0` (Python 3.14 or newer), then
`tsdhn assets install` to fetch the matching model bundle.

Containers: pull `ghcr.io/totallynotdavid/tsdhn-api:v0.2.0`, `tsdhn-web:v0.2.0`,
`tsdhn-backup:v0.2.0` and `tsdhn-toolchain:v0.2.0`, then follow
`docs/deploy.md`. Regenerate the environment file and recreate the database
before starting the new stack.

Report problems at <https://github.com/totallynotdavid/tsdhn/issues>.
