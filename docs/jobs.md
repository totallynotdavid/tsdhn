# Jobs

A simulation passes through the web app, the compute API, a queue, a worker and
MinIO. This page follows it through those stages and states the rules that keep
the stores consistent. [Architecture](architecture.md) says which component owns
what. [Database](database.md) covers the roles.

## Identifiers

| Name              | Owner           | Purpose                                                       |
| ----------------- | --------------- | ------------------------------------------------------------- |
| `simulation_id`   | web app         | Public simulation ID, used again when a submission is retried |
| internal job ID   | compute service | Database and queue ID. Not returned to the web app           |
| output object key | compute service | Private MinIO location                                        |

The public page is `/simulations/{simulation_id}`. The web app creates
`simulation_id` before it calls the compute API and reuses it for every retry.

Repeating a request with the same `simulation_id` and input returns the existing
compute job. Reusing the ID with different input is rejected. A researcher can
retry after a lost response without starting the same simulation twice.

## States

A compute job has four states:

| State       | Meaning                                                       |
| ----------- | ------------------------------------------------------------- |
| `queued`    | The job is waiting for a worker.                              |
| `running`   | A worker owns the current delivery and is running the engine. |
| `completed` | Output metadata and files were stored.                        |
| `failed`    | The simulation cannot continue.                               |

The web page shows the compute state once the compute row exists. Before that it
derives a submission state from its own row:

| Compute row | Submission error | Displayed state     |
| ----------- | ---------------- | ------------------- |
| exists      | any              | the compute status  |
| missing     | set              | `submission_failed` |
| missing     | not set          | `submitting`        |

A successful retry clears the saved submission error.

## Lifecycle

### Submit

1. The web app authenticates the user and validates the form.
2. It creates the simulation ID and saves the input.
3. It sends the ID and input to the compute API with `COMPUTE_API_TOKEN`.
4. The compute API creates the `compute.jobs` row and the queue task in one
   transaction, or returns the existing job for the same ID and input.
5. The browser opens the simulation page.

If the request fails before a compute row can be read, the web app saves a
submission error. The researcher can retry with the same `simulation_id`.

### Run

1. A worker claims the queue task and marks the compute job `running`.
2. It takes the workspace lock and runs the engine in
   `TSDHN_JOBS_DIR/{simulation_id}`.
3. Progress callbacks update the compute job and notify listeners.
4. The worker uploads the output files and their metadata to MinIO.
5. It marks the job `completed` only after the upload succeeds, then removes the
   workspace.

Output responses carry names and filenames, not MinIO object keys.

### Show progress

The web app checks ownership, then reads the simulation and its compute row. For
live progress it relays the compute API event stream to the browser. The compute
service sends the current state, listens for PostgreSQL notifications, and
closes the stream when the job finishes or after
`TSDHN_SSE_MAX_DURATION_SECONDS` (1800).

### Download

1. The browser asks the web app for an output name.
2. The web app checks the session, simulation ownership and available names.
3. The compute API returns a MinIO URL that is valid for
   `TSDHN_OUTPUT_URL_TTL_SECONDS` (900). The compute API answers with a 307
   redirect and the web app passes it on as a 302.
4. The browser downloads the file from MinIO.

Neither the web app nor the compute API relays output bytes.

## Failure and recovery

The worker retries only `TransientInfraError`, which covers PostgreSQL, MinIO
and a workspace still held by an earlier attempt. A job gets three attempts
(`MAX_ATTEMPTS`), with a 15 second backoff that doubles. Invalid input, missing
model files and failed scientific steps fail the job at once, because repeating
them does not change the result.

The engine records its progress in the workspace, so a retry resumes completed
work. See [Pipeline](pipeline.md#resume-behavior).

A worker asked to stop gives its running simulation a short grace period. A
simulation outlasts that, so it is cancelled and its claim goes back to the
queue for another worker, which resumes from the checkpoints.

A worker that dies loses its lease, and the queue reclaims the job. When that
happens on the last attempt, the queue records the failure itself and no running
code is left to update `compute.jobs`. The worker process therefore reconciles
every 60 seconds. It marks as `failed` every job that is terminal in the queue
for more than five minutes and unfinished in `compute.jobs`. The error says the
status was reconciled rather than reported by the run.

The simulation runs on a thread that cannot be stopped on demand, so a replaced
attempt can keep running for a while. The `owner_attempt` fence rejects its
database writes, and the workspace lock keeps the replacement from reading
checkpoints the old thread is still writing.

## Invariants

The queue, the compute row, the workspace and queue retention describe one
simulation in four stores. A process must not infer safety from one store unless
the join or fence stated here also holds.

### Queue

The producer creates one queue row per compute job, with a dedupe key and a
payload that names the job. The worker is the only runtime actor that claims a
pending row, renews its lease and advances it. The queue's lease fence makes a
transition from a superseded attempt fail.

### Compute row

The queue owns delivery, leases and retries. `compute.jobs` owns what a
researcher sees. Retention never deletes `compute.jobs`.

`compute.jobs.owner_attempt` joins the two. It holds the queue's attempt counter
for the delivery that owns the row. Every claim increments the counter, and an
operator retry raises the attempt ceiling instead of resetting the count. A
larger number is always a later delivery, so a guard tells the newest attempt
from a superseded one without locking across systems.

| Transition                                            | Who                                  | Allowed when                                                                                                                                                            |
| ----------------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `queued` (row created, task enqueued)                 | API request                          | The row and its queue entry commit together.                                                                                                                            |
| `queued`, `running`, or `failed` to `running` (claim) | The attempt that was delivered       | It is not superseded (`owner_attempt` is unset or not newer), the job is not `completed`, and, if the job is `failed`, this attempt is newer than the one that owns it. |
| Progress, `completed`, and `failed` (reported)        | The running attempt                  | It still owns the row and the row is not finished.                                                                                                                      |
| `failed` (reconciled)                                 | The worker's reconciliation          | The queue gave up on the job, it has been terminal for more than the grace period, the row is not finished, and no newer attempt has taken the row since.               |
| Restart a finished job                                | An operator, through the queue retry | The job is terminal in the queue. It returns as a newer attempt and claims the row through the claim rule.                                                              |

`completed` is never reclaimed. At-least-once delivery can redeliver a finished
job, and running it again would flip the row back to `running` for everyone
watching. `failed` is reclaimed only by a newer attempt, which is an operator
retry and never a straggler that wakes up after reconciliation.

Reconciliation does not overrule a live attempt. It skips a row that a newer
attempt has taken, and it records the attempt it failed so that a straggler from
that attempt cannot claim the row afterwards. If it races a retry, either order
is safe: the retry's claim supersedes a reconciliation that landed first, and a
reconciliation that would land second is skipped.

### Workspace lock

`TSDHN_JOBS_DIR/{simulation_id}` and its sibling `.lock` file are one unit. The
lock is an operating system `flock`, so the kernel releases it when the holding
process dies.

An attempt takes the exclusive lock before it reads checkpoints or writes the
workspace, and holds it through the result upload. Only the completion path, or
the hourly sweep of workspaces older than 24 hours whose job is terminal, may
remove a workspace, and only after it takes the lock.

The claim is one open file with two shares. The kernel thread holds one and the
coroutine holds the other. The thread releases its share when the simulation
stops. The coroutine releases its share after the upload. The last release
closes the file and so frees the lock. If cancellation wins before the coroutine
receives the claim, a detached drain task releases both shares. If it wins after
the coroutine receives the claim but before the thread starts, the coroutine
releases the thread's share too.

A replacement attempt fails with a transient error while the lock is held, then
retries after its backoff. The sweep skips a workspace whose lock is held.

`flock` protects one host. Workers on different hosts that share a network
volume are not covered. An abandoned thread that never reaches another progress
write keeps the lock until it finishes, and the replacement can use up its
attempts while it waits.

### Queue retention

An hourly pass in the worker deletes a `task_queue.jobs` row when all of these
hold in one database policy:

- the row belongs to this queue;
- its queue state is terminal;
- its `finished_at` is more than seven days old;
- its payload names a canonical compute job UUID;
- the matching `compute.jobs.status` is `completed` or `failed`.

The purger role cannot read `compute.jobs`, so a security-definer function in
the database checks the status. The worker also preselects candidates, but the
database policy is the boundary.

Deleting a queue row cascades to its attempt and occurrence rows. Rows whose
compute counterpart is missing, malformed, recent or still running stay for
reconciliation and inspection. Retention does not delete `compute.jobs`, output
metadata or MinIO objects.
