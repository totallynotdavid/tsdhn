"""Database-free tests for retry policy and payload decoding."""

import uuid

import pytest
from rqueue import PermanentFailure

from api.core.errors import TransientInfraError
from api.core.tasks import MAX_ATTEMPTS, TRANSIENT_RETRY, decode_payload


@pytest.mark.parametrize(
    ("error", "attempt", "retried"),
    [
        (TransientInfraError("db down"), 1, True),
        (TransientInfraError("db down"), MAX_ATTEMPTS - 1, True),
        (TransientInfraError("db down"), MAX_ATTEMPTS, False),
        # retry_on is an allowlist. A pipeline error is terminal on attempt one.
        (RuntimeError("bad epicenter"), 1, False),
        (PermanentFailure("unknown job"), 1, False),
    ],
)
def test_transient_retry_policy(error: Exception, attempt: int, retried: bool) -> None:
    assert TRANSIENT_RETRY.should_retry(error, attempt=attempt) is retried


def test_transient_retry_backs_off_exponentially_from_fifteen_seconds() -> None:
    first = TRANSIENT_RETRY.backoff_seconds(1)
    second = TRANSIENT_RETRY.backoff_seconds(2)

    # Jitter is +/-10%, so these are ranges rather than exact values.
    assert 13.5 <= first <= 16.5
    assert 27.0 <= second <= 33.0


def test_decode_payload_reads_the_compute_job_id() -> None:
    compute_job_id = uuid.uuid4()

    assert decode_payload({"compute_job_id": str(compute_job_id)}) == compute_job_id


@pytest.mark.parametrize(
    "payload",
    [None, [], "compute_job_id", {}, {"compute_job_id": "not-a-uuid"}],
)
def test_decode_payload_rejects_anything_it_cannot_name_a_job_from(
    payload: object,
) -> None:
    # A decode failure is durable in rqueue and costs no retry budget, so it
    # has to raise rather than return a placeholder.
    with pytest.raises((ValueError, KeyError, TypeError)):
        decode_payload(payload)
