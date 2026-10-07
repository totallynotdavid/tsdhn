# Jobs

This guide explains what happens after the web app submits a simulation. The web
application stores the public `simulation_id`. The compute service stores the
internal job, queue delivery, workspace, and output metadata.

## Submit a job

The web app authenticates the researcher, validates the form, creates a
`simulation_id`, and saves the input. Its server code submits that ID and the
input to the compute API with `COMPUTE_API_TOKEN`.

The compute API creates the `compute.jobs` row and its queue entry in one
transaction. A unique `simulation_id` makes a repeated submission return the
existing job when its input is the same. Reusing the ID with different input is
rejected.

The compute row uses four states:

| State       | Meaning                                                       |
| ----------- | ------------------------------------------------------------- |
| `queued`    | The job is waiting for a worker.                              |
| `running`   | A worker owns the current delivery and is running the engine. |
| `completed` | Output metadata and files were stored.                        |
| `failed`    | The simulation cannot continue.                               |

The web page uses the compute state when the row exists. Before the API creates
that row, it shows `submitting` or `submission_failed` from the web record.

## Deliver and claim work

The API producer creates a queue row with a dedupe key and a payload naming the
compute job. The worker is the only runtime process that claims a pending row,
renews its lease, and advances execution. The queue lease fence rejects a
transition from a superseded delivery.

When a worker claims a job, it increments `owner_attempt` and changes the
compute row to `running`. Progress, success, and failure updates are accepted
only from the delivery that owns that row. A later operator retry has a strictly
larger attempt number and can claim a failed job. A stale delivery cannot
reclaim a completed job or overwrite a newer attempt.

The worker holds an operating-system lock on `TSDHN_JOBS_DIR/{simulation_id}`
and its sibling `.lock` while it reads checkpoints, writes the workspace, and
uploads the result. A replacement waits for that lock. A process crash releases
the kernel lock, allowing the next delivery to resume from a valid checkpoint.

## Finish a job

The worker runs the engine, publishes progress, uploads output files to MinIO,
and records output metadata. It marks the compute job `completed` only after the
upload succeeds. Output responses contain names and filenames, not private MinIO
object keys.

If the queue exhausts delivery attempts after a worker dies, the queue can be
terminal before the compute row is. Periodic reconciliation finds such rows
after a grace period and records `failed`. It skips a row that a newer attempt
has claimed. A reported result is not replaced by reconciliation.

## Retain queue history

The worker runs queue retention hourly. It removes a queue row only when the row
belongs to the configured queue, is terminal, is more than seven days old, has a
canonical compute-job UUID, and its matching compute row is `completed` or
`failed`.

Retention removes queue attempt and occurrence rows through the queue's cascade.
It does not delete `compute.jobs`, completed output metadata, or MinIO objects.

## Stream progress and download outputs

The web app checks session ownership before requesting progress or an output.
For progress it relays the compute API event stream to the browser. For an
output it asks the compute API for a short-lived MinIO URL; the browser then
downloads the file directly from MinIO.
