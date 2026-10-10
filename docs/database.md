# Database

The web app and the compute service can share one PostgreSQL server. Separate
schemas and roles keep their writes independent.

The database owner runs migrations and owns every schema and table. Runtime
services connect with restricted roles.

## Web tables

The web app creates and writes its own tables in `public`. The simulation table
holds:

```text
id
user_id
params
submission_error
created_at
```

The web runtime role reads and writes the web tables and reads `compute.jobs`.
It cannot change compute jobs, read queue tables or run schema changes. The
table definition in `apps/web/src/lib/server/db/compute.ts` is used for reads
only and is excluded from web migrations.

## Compute tables

The compute service creates and writes `compute.jobs` and the `task_queue`
schema that rqueue owns. `compute.jobs.simulation_id` links a compute job to the
web simulation. It is unique, so a repeated submission returns the same job.

`tsdhn-compute-migrate` applies the numbered files in
`packages/api/api/migrations/` in name order. It records each applied file in
`compute.schema_migrations` and rolls a failing file back. To change the schema,
add the next numbered file. To rebuild a local database from scratch, run
`mise run db:reset`, which deletes the project-local PostgreSQL cluster under
`.data/postgres`.

## Compute roles

Three restricted runtime roles are provisioned after the compute and queue
migrations by `tsdhn-queue-grants`. None can run schema changes, and row-level
security scopes each to the deployment's queue.

| Role                    | Process          | Queue capability                 | `compute.jobs`     |
| ----------------------- | ---------------- | -------------------------------- | ------------------ |
| `COMPUTE_PRODUCER_ROLE` | API              | enqueue and read (`PRODUCE`)     | `SELECT`, `INSERT` |
| `COMPUTE_WORKER_ROLE`   | worker           | claim and transition (`CONSUME`) | `SELECT`, `UPDATE` |
| `COMPUTE_PURGER_ROLE`   | worker retention | inspect plus delete queue jobs   | none               |

The producer cannot claim a job. The worker cannot insert or delete a queue job.
The purger cannot reach `compute.jobs`. Deleting a queue job cascades to its
attempt history, so retention has its own credential instead of using the
consumer role.

The API, the worker and the purger each need their own configured password. None
falls back to the owner URL, which only migrations and provisioning use.

Each runtime role is `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOBYPASSRLS`,
`NOREPLICATION` and `NOINHERIT`, with no inherited role membership. Provisioning
is repeatable. Running it again removes any grant or membership added by hand.

The web role is provisioned by `tsdhn-compute-migrate` and `tsdhn-web-grants`.
`mise run db-migrate` and the Compose stack run both. See [Deploy](deploy.md).
