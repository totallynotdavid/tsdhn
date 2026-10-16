from datetime import datetime

__all__ = ["OutputsExpiredError", "TransientInfraError"]


class TransientInfraError(Exception):
    """An infrastructure error that is safe to retry."""


class OutputsExpiredError(Exception):
    """The retention pass deleted this job's output files."""

    def __init__(self, expired_at: datetime) -> None:
        super().__init__(f"Output files expired on {expired_at.date().isoformat()}")
        self.expired_at = expired_at
