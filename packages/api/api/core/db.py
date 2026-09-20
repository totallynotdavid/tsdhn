"""The process-wide asyncpg pool, shared by the API and the worker.

Both processes open one pool with `open_pool` and borrow a connection per
statement or transaction. Nothing holds a connection across a simulation. The
one long-lived borrow is the LISTEN connection `rqueue.Worker` holds, which is
why `settings.worker_pool_size()` sizes the worker's pool as it does.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from api.core.errors import TransientInfraError
from api.core.settings import COMPUTE_DATABASE_URL, role_database_url

__all__ = [
    "COMPUTE_DATABASE_URL",
    "CONNECT_TIMEOUT",
    "JobRow",
    "acquire",
    "close_pool",
    "connect",
    "get_pool",
    "is_transient",
    "notify_channel",
    "open_pool",
    "runtime_dsn",
    "transient_connection_errors",
]

JobRow = dict[str, Any]
CONNECT_TIMEOUT = 2

_pool: asyncpg.Pool | None = None

# The DSN the open pool used, so `connect()` reaches the same role instead of
# falling back to the owner.
_dsn: str | None = None

# Client-side failures: the server was never reached, or the socket died.
_CLIENT_ERRORS = (ConnectionError, OSError, TimeoutError)

# Server-side failures are classified by SQLSTATE class, not by exception type.
# An enumerated tuple of asyncpg classes misses cases. `TooManyConnectionsError`
# is an `InsufficientResourcesError`, not a `PostgresConnectionError`.
#
#   08  connection_exception     the connection broke or was refused
#   53  insufficient_resources   too many connections, out of memory, disk full
#   57  operator_intervention    admin shutdown, crash shutdown, cannot connect now
#   40  transaction_rollback     serialization failure, deadlock detected
#
# The classes are deliberately wide. Misclassifying a transient failure as
# permanent discards a simulation that would have succeeded, which costs tens
# of minutes of compute and an operator retry. Misclassifying a permanent
# failure as transient costs two extra attempts and about 45 seconds of
# backoff. A few permanent members inside these classes, such as 57P04
# database_dropped, are an acceptable price for catching every transient one.
#
# Classes 22 (data exception), 23 (integrity constraint), and 42 (syntax and
# access rules) are excluded. They are application bugs, and a retry would
# rerun a whole simulation to reach the same failure.
_TRANSIENT_SQLSTATE_CLASSES = frozenset({"08", "40", "53", "57"})


def is_transient(exc: BaseException) -> bool:
    """Whether this failure could plausibly succeed on a later attempt."""
    if isinstance(exc, _CLIENT_ERRORS):
        return True
    sqlstate = getattr(exc, "sqlstate", None)
    return isinstance(sqlstate, str) and sqlstate[:2] in _TRANSIENT_SQLSTATE_CLASSES


def runtime_dsn(role: str, password: str) -> str:
    """Resolve a runtime role's DSN, failing before an owner fallback."""
    try:
        return role_database_url(role, password)
    except ValueError as error:
        raise RuntimeError(str(error)) from error


async def open_pool(*, min_size: int, max_size: int, dsn: str) -> asyncpg.Pool:
    """Create the process-wide pool. Idempotent within one process.

    The DSN is required so a runtime caller cannot accidentally become the
    schema owner by omitting role credentials.
    """
    global _pool, _dsn
    if _pool is None:
        _dsn = dsn
        _pool = await asyncpg.create_pool(
            _dsn,
            min_size=min_size,
            max_size=max_size,
            timeout=CONNECT_TIMEOUT,
        )
    return _pool


async def close_pool() -> None:
    global _pool, _dsn
    if _pool is not None:
        await _pool.close()
        _pool = None
    _dsn = None


def get_pool() -> asyncpg.Pool:
    """Return the open pool, or explain that startup did not open one."""
    if _pool is None:
        raise RuntimeError("database pool is not open; call db.open_pool() first")
    return _pool


@asynccontextmanager
async def transient_connection_errors(
    connection: asyncpg.Connection,
) -> AsyncIterator[None]:
    """Translate a connection lost mid-statement into `TransientInfraError`.

    `acquire()` covers only the borrow. asyncpg reports a connection that dies
    around a statement in two ways:

    - The backend dies with the statement in flight. asyncpg raises
      `ConnectionDoesNotExist` (SQLSTATE 08003), which `is_transient`
      recognises.
    - The backend is already gone when the statement is issued. asyncpg raises
      a bare `InterfaceError("connection is closed")`.

    `InterfaceError` is also raised for programming errors such as a wrong
    argument count, so it is translated only when the connection is gone.
    `TRANSIENT_RETRY` retries `TransientInfraError`, so translating a bug would
    spend a job's retry budget on something that cannot succeed. A programming
    error leaves the connection open and propagates unchanged.
    """
    try:
        yield
    except asyncpg.InterfaceError as e:
        if not _connection_is_gone(connection):
            raise
        raise TransientInfraError("database unavailable") from e
    except Exception as e:
        if not is_transient(e):
            raise
        raise TransientInfraError("database unavailable") from e


def _connection_is_gone(connection: asyncpg.Connection) -> bool:
    """Whether this connection can still be used at all.

    `is_closed()` alone is not enough. When a pooled connection's backend
    dies, the pool terminates the connection and takes the proxy back. After
    that every method on the proxy raises `InterfaceError`, `is_closed()`
    included. A proxy that cannot answer is gone, while a connection that only
    rejected a malformed call answers `False` and keeps working.
    """
    try:
        return bool(connection.is_closed())
    except asyncpg.InterfaceError:
        return True


@asynccontextmanager
async def acquire() -> AsyncIterator[asyncpg.Connection]:
    """Borrow a pooled connection for one statement or one transaction."""
    pool = get_pool()
    try:
        connection = await pool.acquire()
    except Exception as e:
        # Pool exhaustion arrives as `TooManyConnectionsError` (53300), which is
        # as retryable as a refused socket.
        if not is_transient(e):
            raise
        raise TransientInfraError("database unavailable") from e
    try:
        yield connection
    finally:
        await pool.release(connection)


async def connect() -> asyncpg.Connection:
    """Open a connection outside the pool.

    The SSE endpoint holds one for the lifetime of a stream, up to
    `SSE_MAX_DURATION`. Taking those from the request pool would let a few
    watching browsers starve every other route.
    """
    if _dsn is None:
        raise RuntimeError(
            "database connection DSN is not configured; "
            "call db.open_pool() with a runtime-role DSN first"
        )
    try:
        return await asyncpg.connect(
            _dsn,
            timeout=CONNECT_TIMEOUT,
        )
    except Exception as e:
        if not is_transient(e):
            raise
        raise TransientInfraError("database unavailable") from e


def notify_channel(simulation_id: uuid.UUID) -> str:
    """Return the SQL-safe notification channel for one job."""
    return f"tsdhn_job_{simulation_id.hex}"
