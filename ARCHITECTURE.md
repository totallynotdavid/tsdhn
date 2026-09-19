# Architecture

This document explains what each component owns and how a simulation moves
through the system. Component READMEs explain how to work on each component.
`DEPLOY.md` explains how to run the services.

## System

```text
Browser
  |
  v
SvelteKit web app
  |-- users, sessions, and simulations in public
  |-- reads current jobs from compute.jobs
  |
  v
FastAPI compute service
  |-- compute.jobs and the rqueue task_queue schema
  |-- worker -> tsdhn engine -> MinIO
```

The browser talks to the web app. The web app checks the session and handles
the researcher-facing flow. Its server code calls the compute API at
`COMPUTE_API_URL` with `COMPUTE_API_TOKEN`. The browser never receives the
token and never calls the compute API directly.

The web app and compute service may use the same PostgreSQL server. Separate
schemas and database roles keep their writes independent.

## Responsibilities

### Web app

The web app owns:

- users, sessions, accounts, and verification records;
- `simulation_id`, user ID, submitted parameters, and creation time;
- failures that happen while submitting a simulation to the compute service;
- authentication, ownership checks, and user-facing responses;
- joining the simulation with current compute state for display.

The web app does not store compute progress, queue state, an internal compute
job ID, a compute-service selector, or output storage keys.

### Compute service

The compute service owns:

- the API used by the web server;
- `compute.jobs` and the `task_queue` schema rqueue owns;
- the internal compute job ID;
- job progress, retry state, and worker heartbeats;
- simulation work directories and checkpoints;
- output metadata and uploads to MinIO.

The compute service receives a `simulation_id` from the web app. It does not
know about web sessions, users, or passwords.

### Simulation engine

The `tsdhn` package owns the scientific calculation, pipeline order, run
directory, checkpoints, and output files. It has no dependency on web users,
PostgreSQL jobs, queues, or MinIO.

The engine preserves several numerical and file-format rules from the original
MATLAB and Fortran programs. Those rules are documented with the engine and
beside the code that implements them. Legacy behavior is compatibility
evidence. It is not scientific validation without a source.

### Output storage

The worker may use local disk while a simulation is running. That work
directory contains intermediate files and checkpoints needed for recovery.

MinIO stores completed output files. The compute database stores their names,
media types, filenames, and private object keys. Public API responses omit the
object keys.

## Database ownership

The database owner runs migrations and owns all schemas and tables. Runtime
services use restricted roles.

The web app creates and writes only its tables in `public`. Its simulation
table contains:

```text
id
user_id
params
submission_error
created_at
```

The compute service creates and writes `compute.jobs` and the `task_queue`
schema rqueue owns. `compute.jobs.simulation_id` links a compute job to the web
simulation. The value is unique because repeating a submission must return the
same compute job.

The web runtime role can read and write the web tables and read
`compute.jobs`. It cannot change compute jobs, read queue tables, or run schema
changes. The table definition in `apps/web/src/lib/server/db/compute.ts` is
used only for reads and is excluded from web migrations.

The compute service has three restricted runtime roles, provisioned after the
compute and queue migrations by `tsdhn-queue-grants`. None can run schema
changes, and row-level security scopes each to the deployment's queue:

| Role | Process | Queue capability | `compute.jobs` |
| --- | --- | --- | --- |
| `COMPUTE_PRODUCER_ROLE` | API | enqueue and read (`PRODUCE`) | `SELECT`, `INSERT` |
| `COMPUTE_WORKER_ROLE` | worker | claim and transition (`CONSUME`) | `SELECT`, `UPDATE` |
| `COMPUTE_PURGER_ROLE` | worker retention | inspect plus delete queue jobs | none |

The producer cannot claim a job. The worker cannot insert or delete a queue
job. The purger cannot reach `compute.jobs`. Deleting a queue job cascades to
its attempt history, so retention uses its own credential rather than the
consumer role.

The schema-owner connection is used only for migrations and provisioning. The
API, worker, and purger each require their own configured password and never
fall back to the owner URL.

Provisioning is repeatable and only narrows. Each runtime role is
`NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOBYPASSRLS`, `NOREPLICATION`,
and `NOINHERIT`, with no inherited role membership. A manual grant or a
template role must not widen a runtime capability.

## Cross-boundary invariants

The queue, the compute row, the workspace, and queue retention describe one
simulation in different stores. A change to any of them must keep the rules
below. A process must not infer safety from a state in another store unless the
stated join or fence also holds.

### Queue state

The producer creates one queue row for a compute job, with a dedupe key and a
payload naming that job. The worker is the only runtime actor that claims a
pending row, renews its lease, and advances it through execution. rqueue's
lease fence makes a superseded attempt's transition fail. Queue finalization
can produce a terminal row without the handler updating `compute.jobs`, which
is why reconciliation exists.

### Compute state

The queue owns delivery, leases, and retries. `compute.jobs` owns what a
researcher sees. Different actors update them at different times, so the rules
below keep them from disagreeing. The failures they prevent are silent ones,
such as a job that reads `running` forever or a finished result that is
overwritten.

`compute.jobs` is the application record. Retention never deletes it.

`compute.jobs.owner_attempt` links the two systems. It holds the queue's
attempt counter for the delivery that currently owns the row. The counter only
increases. Every claim increments it, and an operator retry raises the attempt
ceiling instead of resetting the count. A larger number therefore always means
a later delivery, and a guard can tell the newest attempt from a superseded one
without locking across systems.

| Transition | Who | Allowed when |
| --- | --- | --- |
| `queued` (row created, task enqueued) | API request | The job row and its queue entry commit together, so a job always has an entry. |
| `queued`, `running`, or `failed` to `running` (claim) | The attempt that was just delivered | It is not superseded (`owner_attempt` is unset or not newer), the job is not `completed`, and, if the job is `failed`, this attempt is strictly newer than the one that owns it. |
| Progress, `completed`, and `failed` (reported) | The running attempt | It still owns the row and the row is not finished. |
| `failed` (reconciled) | The worker's periodic reconciliation | The queue has given up on the job, it has been terminal longer than the grace period, the row is not finished, and no newer attempt has taken the row since. |
| Restart a finished job | An operator, through the queue's retry API | The job is terminal in the queue. It comes back as a strictly newer attempt and claims the row through the claim rule above. |

A completed job is never reopened. `completed` is never reclaimed, because
at-least-once delivery can redeliver a finished job and re-running it would
flip the row back to `running` for everyone watching. `failed` can be
reclaimed only by a strictly newer attempt. That is an operator retry and
never a straggler waking up after its job was reconciled.

Reconciliation never overrules a live attempt. It exists for the case where
nothing is left running to report an outcome. It skips any row that a newer
attempt has taken, and it records the attempt it failed so a straggler from
that attempt cannot claim the row afterwards. If it races a retry, either
order is safe. The retry's claim supersedes a reconciliation that landed first,
and a reconciliation that would land second is skipped.

### Workspace and lock state

`TSDHN_JOBS_DIR/{simulation_id}` and its sibling `.lock` are one workspace
state, not independent scratch files. The lock is an operating system `flock`,
so it is released even when the holding process dies without warning.

An attempt must claim the exclusive lock before reading checkpoints or writing
the engine workspace. The claim stays held through the result upload. A
superseded attempt cannot write to the database after the fence rejects it, and
the lock keeps it from writing files a replacement is reading. A process crash
releases the kernel lock so a replacement attempt can resume. Only the owning
completion path, or the abandoned-work sweep for an old terminal compute row,
may remove the workspace. Removal must take the lock before unlinking it.

The claim has five states:

- `unclaimed`: no attempt holds the lock.
- `held-by-kernel-thread`: the claiming thread acquired the lock.
- `held-by-coroutine-after-shield-returns`: the normal handoff reached the
  coroutine.
- `held-by-drain-task-after-cancellation`: cancellation won before that
  handoff, and a detached drain task owns the returned claim.
- `released`: every share has been given back and the descriptor is closed.

The claiming thread alone moves `unclaimed` to `held-by-kernel-thread`. On the
normal path the coroutine then moves the claim to
`held-by-coroutine-after-shield-returns`. The kernel thread gives back its
share when the simulation stops, and the coroutine gives back its share after
the result upload. If cancellation wins after the handoff but before the kernel
thread starts, the coroutine also gives back the kernel share because no kernel
`finally` will run. After the kernel starts, only that thread gives back its
share. If cancellation wins before the coroutine receives the claim, the drain
task moves it to `held-by-drain-task-after-cancellation` and gives back both
shares. Only the last release moves the claim to `released`.

The sweep may remove a workspace only while it is `unclaimed`. A busy lock
leaves the state unchanged, and a workspace the sweep locks is removed and left
`released`.

A redelivered attempt can enter its own held state only after the previous
claim is released. The drain gives back both shares before the lock becomes
available, and `claim_workspace` and the sweep back off while the lock is held.
No replacement can write into a workspace that a drain task is still
releasing.

`flock` protects a single host only. Workers on different hosts that share one
network volume are not covered.

### Purge state

Queue retention deletes a `task_queue.jobs` row only when all of these hold in
the same database policy:

- the row belongs to this queue;
- its queue state is terminal;
- its `finished_at` is more than seven days old;
- its payload names a canonical compute job UUID;
- the matching `compute.jobs.status` is `completed` or `failed`.

An hourly pass in the worker process runs retention. The database
security-definer predicate enforces the cross-schema status check while keeping
`compute.jobs` hidden from the purger. The worker also preselects candidates
through its compute-readable pool, but that check is advisory. The database
policy is the boundary.

Rows whose compute counterpart is missing, malformed, recent, or still running
remain available for reconciliation and inspection. Deleting a queue row
cascades to its attempt and occurrence rows. The queue row has no application
value once the handler records the outcome, and the week keeps attempt history
available for operational inspection.

## Identifiers

| Name | Owner | Purpose |
| --- | --- | --- |
| `simulation_id` | web app | Public simulation ID, used again when a submission is retried |
| internal job ID | compute service | Database and queue ID; never returned to the web app |
| output object key | compute service | Private MinIO location |

The public page is `/simulations/{simulation_id}`. The web app creates
`simulation_id` before calling the compute API and uses the same value for
every retry.

Repeating a request with the same `simulation_id` and input returns the
existing compute job. Reusing the ID with different input is rejected. A
researcher can therefore retry after a lost response without starting the
same simulation twice.

## Displayed state

The compute row is the current record once it exists. Before then, the web app
derives a short submission state from its own row:

```text
compute row exists                  use the compute job status
no compute row, submission error    submission_failed
no compute row, no error            submitting
```

A stale submission error never overrides an existing compute row. A successful
retry clears the saved submission error.

Compute jobs use these states:

```text
queued     waiting for a worker
running    executing the simulation
completed  output metadata and files were stored
failed     the simulation cannot continue
```

## Submit a simulation

1. The web app authenticates the user and validates the form.
2. It creates the simulation ID and saves the user input.
3. It sends the ID and input to the compute API.
4. The compute service creates the job and queue task in one database
   transaction, or returns the existing job for the same ID and input.
5. The browser opens the simulation page.

If the request fails before a compute row can be read, the web app saves a
submission error. The researcher can retry with the same `simulation_id`.

## Run a simulation

1. A worker claims the queue task.
2. It marks the compute job as running.
3. It runs the engine in `TSDHN_JOBS_DIR/{simulation_id}`.
4. Progress callbacks update the compute job and notify listeners.
5. The worker uploads completed output files and their metadata to MinIO.
6. It marks the job as completed only after storage succeeds.

## Show progress

The web app checks ownership, then reads the simulation and its compute row.
For live progress, it relays the compute API event stream to the browser. The
compute service sends the current state, listens for PostgreSQL notifications,
and closes the stream when the job finishes or the configured stream lifetime
ends.

## Download an output file

1. The browser asks the web app for an output name.
2. The web app checks the session, simulation ownership, and available names.
3. The compute API creates a short-lived MinIO URL.
4. The browser downloads the file directly from MinIO.

The web app and compute API do not relay output bytes.

## Failure and recovery

The compute service retries temporary failures in PostgreSQL, MinIO, or other
services. Invalid input, missing model files, and failed scientific steps do
not become more likely to succeed when repeated, so they fail the job.

The engine records enough state to continue valid completed work after a
retry. The compute service keeps the job in `compute.jobs` and reports the
final failure when retries are exhausted. Deployment settings determine retry
limits, worker recovery, storage, and cleanup.

A worker asked to stop gracefully stops taking new work and gives what it is
already running a short grace period. A simulation runs far longer than that, so
it is cancelled and its claim is handed straight back for another worker, which
resumes from the checkpoints in the job's work directory.

A worker that dies mid-run loses its lease, and the queue reclaims the job
without asking the dead worker anything. When that happens on the job's last
attempt the queue records the failure by itself, so no running code is left to
update `compute.jobs`. The worker process therefore reconciles. It periodically
finds jobs the queue has given up on that `compute.jobs` still shows as
unfinished, and marks them failed with an error saying the status was
reconciled rather than reported by the run. A job that reported its own outcome
is never overwritten.

The simulation runs on a thread that the service cannot stop on demand, so a
replaced attempt can keep running for a while. The `owner_attempt` fence
rejects its database writes. The workspace lock keeps a replacement from
reading checkpoints that the old thread is still writing. If the worker process
dies, the kernel releases the lock and the replacement resumes. If the previous
attempt is still running, the replacement fails with a transient error and
retries after a backoff. See [Cross-boundary invariants](#cross-boundary-invariants)
for the rules.
