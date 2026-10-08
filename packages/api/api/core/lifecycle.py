"""Job lifecycle values that Python code and SQL generated here must agree on."""

from datetime import timedelta

from tsdhn.domain import JobStatus

__all__ = ["JOB_ID_RE", "JOB_RETENTION", "TERMINAL_STATUSES"]

# A queue row is purged this long after it finishes. `compute.jobs` is never
# purged.
JOB_RETENTION = timedelta(days=7)

# `compute.jobs` uses application statuses, not rqueue's states. A job that
# reached one of these is never overwritten, and its queue row may be purged.
TERMINAL_STATUSES = (JobStatus.COMPLETED.value, JobStatus.FAILED.value)

# The form `str(uuid.UUID(...))` produces, and the only one `enqueue_simulation`
# writes. SQL tests a queue payload against it before a `::uuid` cast so that a
# malformed payload skips its row instead of aborting the statement.
JOB_ID_RE = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
