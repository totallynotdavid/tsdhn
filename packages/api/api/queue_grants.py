"""Provision the least-privilege roles the API and worker connect as.

`tsdhn-compute-migrate` owns the compute schema and the web role;
`rqueue ... migrate` owns the queue schema. This runs after both, for the same
reason `tsdhn-web-grants` runs after the web migrations: a GRANT needs the
tables to exist. Everything here is idempotent, and re-running it narrows a
role that has been over-granted back to the table below.

| role                | queue schema                          | compute schema |
| ------------------- | ------------------------------------- | -------------- |
| COMPUTE_PRODUCER    | `Capability.PRODUCE`                  | SELECT, INSERT |
| COMPUTE_WORKER      | `Capability.CONSUME`                  | SELECT, UPDATE |
| COMPUTE_PURGER      | `Capability.INSPECT` + DELETE on jobs | none           |

`provision_role` grants no DDL to any of them, and this module repairs the
older rqueue capability grant that gives CONSUME INSERT on `jobs`.
Row-level security scopes `jobs` and `job_attempts` to the one queue this
deployment runs;
`concurrency_slots` and `runtime_heartbeats` have no per-queue RLS in rqueue
today, which is fine for this single-queue deployment.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import asyncpg
from rqueue.errors import ValidationError
from rqueue.limits import MAX_QUEUE_NAME_LENGTH, validate_name
from rqueue.models import TERMINAL_STATES
from rqueue.roles import Capability, provision_role, revoke_role

from api.core.settings import (
    APP_DB_ROLE,
    COMPUTE_DATABASE_URL,
    COMPUTE_PRODUCER_PASSWORD,
    COMPUTE_PRODUCER_ROLE,
    COMPUTE_PURGER_PASSWORD,
    COMPUTE_PURGER_ROLE,
    COMPUTE_QUEUE,
    COMPUTE_QUEUE_SCHEMA,
    COMPUTE_WORKER_PASSWORD,
    COMPUTE_WORKER_ROLE,
)

__all__ = ["QueueRole", "provision_queue_roles", "queue_roles"]

logger = logging.getLogger(__name__)

_PURGER_DELETE_FUNCTION = "compute_purger_can_delete"
_PURGE_RETENTION_DAYS = 7
_COMPUTE_TERMINAL_STATUSES = ("completed", "failed")
_COMPUTE_JOB_ID_RE = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_ROLE_STATE_TABLE = "queue_runtime_roles"
_ROLE_KINDS = ("producer", "worker", "purger")
_DEFAULT_PRIVILEGE_OBJECT_TYPES = {
    "r": "TABLES",
    "S": "SEQUENCES",
    "f": "FUNCTIONS",
    "T": "TYPES",
}

# rqueue's role provisioner at the pinned dependency revision only resets ACLs.
# These role attributes and memberships are authority above an ACL, so they
# need their own repair before a runtime password is handed to a process.
_ROLE_ATTRIBUTES = (
    ("rolsuper", "NOSUPERUSER"),
    ("rolcreatedb", "NOCREATEDB"),
    ("rolcreaterole", "NOCREATEROLE"),
    ("rolbypassrls", "NOBYPASSRLS"),
    ("rolreplication", "NOREPLICATION"),
    ("rolinherit", "NOINHERIT"),
)


@dataclass(frozen=True)
class QueueRole:
    """One runtime role: what it may do to the queue, and to `compute.jobs`."""

    name: str
    password: str
    #: The environment variable the password comes from, for error messages.
    env_var: str
    capabilities: tuple[Capability, ...]
    #: Privileges on `compute.jobs`; empty means the role never reaches it.
    compute_privileges: str = ""
    #: Queue-table privileges no capability's grant set covers.
    extra_queue_privileges: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def queue_roles() -> tuple[QueueRole, ...]:
    """The roles this deployment runs, read from settings at call time."""
    return (
        QueueRole(
            name=COMPUTE_PRODUCER_ROLE,
            password=COMPUTE_PRODUCER_PASSWORD,
            env_var="COMPUTE_PRODUCER_PASSWORD",
            # The API only enqueues and reads back. It never touches schedules
            # or queue pauses, which is all INSPECT would add over PRODUCE.
            capabilities=(Capability.PRODUCE,),
            # `create_or_get_job` inserts and reads; no route updates a row.
            compute_privileges="SELECT, INSERT",
        ),
        QueueRole(
            name=COMPUTE_WORKER_ROLE,
            password=COMPUTE_WORKER_PASSWORD,
            env_var="COMPUTE_WORKER_PASSWORD",
            capabilities=(Capability.CONSUME,),
            # The worker only ever advances rows the API created.
            compute_privileges="SELECT, UPDATE",
        ),
        QueueRole(
            name=COMPUTE_PURGER_ROLE,
            password=COMPUTE_PURGER_PASSWORD,
            env_var="COMPUTE_PURGER_PASSWORD",
            # `Admin.purge` reads the terminal rows it is about to remove.
            capabilities=(Capability.INSPECT,),
            # Retention is a queue-only concern: compute.jobs keeps its own
            # history, and this task is not the one to start expiring it.
            compute_privileges="",
            # No capability carries DELETE, on purpose -- a consumer that can
            # delete a job can erase its own attempt history with it. Purge
            # needs exactly this one grant and nothing else.
            extra_queue_privileges=(("jobs", "DELETE"),),
        ),
    )


async def _ddl(connection: asyncpg.Connection, template: str, *args: str) -> None:
    """Run one DDL statement with PostgreSQL doing the identifier quoting.

    The same trick `rqueue.roles` uses: role, schema and table names have no
    bind-parameter form, so `format(..., %I)` is evaluated server-side and only
    its already-quoted result is executed.
    """
    placeholders = ", ".join(f"${index + 2}::text" for index in range(len(args)))
    statement = await connection.fetchval(
        f"SELECT format($1::text, {placeholders})", template, *args
    )
    await connection.execute(statement)


async def _grant_compute_access(
    connection: asyncpg.Connection, role: QueueRole
) -> None:
    """Give one role its `compute.jobs` privileges, and only those.

    The revoke comes first so re-running repairs a role that was widened by
    hand, matching what `migrate.provision_web_role` does for the web role.
    """
    await _ddl(connection, "REVOKE ALL PRIVILEGES ON compute.jobs FROM %I", role.name)
    await _ddl(connection, "REVOKE CREATE ON SCHEMA compute FROM %I", role.name)
    if not role.compute_privileges:
        await _ddl(connection, "REVOKE USAGE ON SCHEMA compute FROM %I", role.name)
        return
    await _ddl(connection, "GRANT USAGE ON SCHEMA compute TO %I", role.name)
    await _ddl(
        connection,
        f"GRANT {role.compute_privileges} ON compute.jobs TO %I",
        role.name,
    )


async def _reset_default_privileges(connection: asyncpg.Connection, role: str) -> None:
    """Remove direct default ACLs that would widen future managed-schema tables."""
    schemas = tuple(dict.fromkeys(("compute", COMPUTE_QUEUE_SCHEMA)))
    defaults = await connection.fetch(
        """
        SELECT DISTINCT owner.rolname AS grantor,
                        namespace.nspname AS schema_name,
                        defaults.defaclobjtype AS object_type
        FROM pg_default_acl AS defaults
        JOIN pg_roles AS owner ON owner.oid = defaults.defaclrole
        LEFT JOIN pg_namespace AS namespace
            ON namespace.oid = defaults.defaclnamespace
        CROSS JOIN LATERAL aclexplode(defaults.defaclacl) AS acl
        JOIN pg_roles AS grantee ON grantee.oid = acl.grantee
        WHERE grantee.rolname = $1
          AND (
              defaults.defaclnamespace = 0
              OR namespace.nspname = ANY($2::text[])
          )
        ORDER BY owner.rolname, namespace.nspname, defaults.defaclobjtype
        """,
        role,
        schemas,
    )
    for default in defaults:
        raw_object_type = default["object_type"]
        if isinstance(raw_object_type, bytes):
            raw_object_type = raw_object_type.decode()
        object_type = _DEFAULT_PRIVILEGE_OBJECT_TYPES.get(str(raw_object_type))
        if object_type is None:
            continue
        grantor = str(default["grantor"])
        schema_name = default["schema_name"]
        if schema_name is None:
            await _ddl(
                connection,
                "ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE ALL PRIVILEGES ON "
                f"{object_type} FROM %I",
                grantor,
                role,
            )
        else:
            await _ddl(
                connection,
                "ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I "
                "REVOKE ALL PRIVILEGES ON "
                f"{object_type} FROM %I",
                grantor,
                str(schema_name),
                role,
            )


async def _reset_role_security(connection: asyncpg.Connection, role: str) -> None:
    """Remove PostgreSQL authority that table ACLs cannot narrow.

    The pinned rqueue provisioner repairs grants but leaves role attributes and
    memberships untouched. A SUPERUSER, BYPASSRLS, CREATEROLE, inherited group
    membership, or default ACL would therefore make the capability table
    misleading.
    """
    current = await connection.fetchrow(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, "
        "rolreplication, rolinherit FROM pg_roles WHERE rolname = $1",
        role,
    )
    if current is None:  # pragma: no cover - provision_role just created it
        return
    clauses = "".join(
        f" {clause}" for column, clause in _ROLE_ATTRIBUTES if current[column]
    )
    if clauses:
        await _ddl(connection, "ALTER ROLE %I" + clauses, role)

    await _reset_default_privileges(connection, role)

    memberships = await connection.fetch(
        """
        SELECT granted.rolname AS granted,
               member.rolname AS member,
               grantor.rolname AS grantor
        FROM pg_auth_members AS membership
        JOIN pg_roles AS granted ON granted.oid = membership.roleid
        JOIN pg_roles AS member ON member.oid = membership.member
        JOIN pg_roles AS grantor ON grantor.oid = membership.grantor
        WHERE member.rolname = $1 OR granted.rolname = $1
        ORDER BY granted.rolname, member.rolname, grantor.rolname
        """,
        role,
    )
    if not memberships:
        return

    server_version: int = await connection.fetchval(
        "SELECT current_setting('server_version_num')::integer"
    )
    if server_version >= 160000:
        for membership in memberships:
            await _ddl(
                connection,
                "REVOKE %I FROM %I GRANTED BY %I",
                membership["granted"],
                membership["member"],
                membership["grantor"],
            )
    else:
        for granted, member in sorted(
            {
                (membership["granted"], membership["member"])
                for membership in memberships
            }
        ):
            await _ddl(connection, "REVOKE %I FROM %I", granted, member)


async def _grant_purger_delete_policy(
    connection: asyncpg.Connection, role: QueueRole
) -> None:
    """Restrict direct purger deletes to rows safe for retention removal.

    The purger has no grant on ``compute.jobs``. The security-definer helper is
    owned by the schema-owner connection that runs provisioning, and is granted
    only to this role, so its result can be part of the RLS policy without
    widening the purger's direct visibility into the compute schema.
    """
    status_literals = ", ".join(f"'{status}'" for status in _COMPUTE_TERMINAL_STATUSES)
    function_body = """
        SELECT CASE
            WHEN payload->>'compute_job_id' !~* __UUID_RE__
                THEN false
            ELSE EXISTS (
                SELECT 1
                FROM compute.jobs AS compute_job
                WHERE compute_job.id = CASE
                    WHEN payload->>'compute_job_id' ~* __UUID_RE__
                        THEN (payload->>'compute_job_id')::uuid
                    ELSE NULL::uuid
                END
                  AND compute_job.status = ANY (ARRAY[__TERMINAL_STATUSES__]::text[])
            )
        END
    """.replace("__UUID_RE__", f"'{_COMPUTE_JOB_ID_RE}'").replace(
        "__TERMINAL_STATUSES__", status_literals
    )
    await _ddl(
        connection,
        "CREATE OR REPLACE FUNCTION %I.%I(payload jsonb) "
        "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER "
        "SET search_path = pg_catalog AS %L",
        COMPUTE_QUEUE_SCHEMA,
        _PURGER_DELETE_FUNCTION,
        function_body,
    )
    await _ddl(
        connection,
        "REVOKE ALL PRIVILEGES ON FUNCTION %I.%I(jsonb) FROM PUBLIC",
        COMPUTE_QUEUE_SCHEMA,
        _PURGER_DELETE_FUNCTION,
    )
    await _ddl(
        connection,
        "GRANT EXECUTE ON FUNCTION %I.%I(jsonb) TO %I",
        COMPUTE_QUEUE_SCHEMA,
        _PURGER_DELETE_FUNCTION,
        role.name,
    )

    policy_name = "compute_purger_terminal_delete"
    await _ddl(
        connection,
        "DROP POLICY IF EXISTS %I ON %I.%I",
        policy_name,
        COMPUTE_QUEUE_SCHEMA,
        "jobs",
    )
    state_placeholders = ", ".join("%L" for _ in TERMINAL_STATES)
    await _ddl(
        connection,
        "CREATE POLICY %I ON %I.%I AS RESTRICTIVE FOR DELETE TO %I "
        f"USING (state = ANY(ARRAY[{state_placeholders}]::text[]) "
        "AND finished_at IS NOT NULL "
        f"AND finished_at < CURRENT_TIMESTAMP - INTERVAL "
        f"'{_PURGE_RETENTION_DAYS} days' "
        "AND %I.%I(payload))",
        policy_name,
        COMPUTE_QUEUE_SCHEMA,
        "jobs",
        role.name,
        *TERMINAL_STATES,
        COMPUTE_QUEUE_SCHEMA,
        _PURGER_DELETE_FUNCTION,
    )


def _validate_role_names(roles: tuple[QueueRole, ...]) -> None:
    """Reject runtime roles that could overwrite another database role."""
    role_env_vars = (
        "COMPUTE_PRODUCER_ROLE",
        "COMPUTE_WORKER_ROLE",
        "COMPUTE_PURGER_ROLE",
    )
    names = [role.name for role in roles]
    if len(names) != len(set(names)):
        raise ValueError(
            "COMPUTE_PRODUCER_ROLE, COMPUTE_WORKER_ROLE, and "
            "COMPUTE_PURGER_ROLE must be pairwise distinct"
        )
    protected = (
        ("APP_DB_ROLE", APP_DB_ROLE),
        ("COMPUTE_DATABASE_URL username", urlsplit(COMPUTE_DATABASE_URL).username),
    )
    for env_var, role in zip(role_env_vars, roles, strict=True):
        for protected_name, protected_value in protected:
            if protected_value and role.name == protected_value:
                raise ValueError(
                    f"{env_var}={role.name!r} collides with "
                    f"{protected_name}={protected_value!r}"
                )


def _validate_compute_queue() -> None:
    """Reject queue targets that the runtime ``Queue`` would reject."""
    try:
        validate_name(
            COMPUTE_QUEUE,
            kind="queue name",
            max_length=MAX_QUEUE_NAME_LENGTH,
        )
    except ValidationError as exc:
        raise ValueError(f"COMPUTE_QUEUE={COMPUTE_QUEUE!r} is invalid: {exc}") from exc


async def _validate_existing_role_names(
    connection: asyncpg.Connection, roles: tuple[QueueRole, ...]
) -> None:
    """Refuse to narrow an unmanaged role that is already security-sensitive.

    A role with a row in rqueue's grant table was provisioned by this module in
    an earlier run, so repairing its drift is intentional. An unrelated role
    must not be passed to ``provision_role`` and then have its attributes or
    memberships stripped merely because an environment variable was mistyped.
    Even an otherwise ordinary pre-existing role must use a fresh configured
    name; only the grant-table marker permits an existing role to be repaired.
    """
    names = [role.name for role in roles]
    existing = await connection.fetch(
        """
        SELECT role_info.rolname,
               role_info.rolsuper,
               role_info.rolcreatedb,
               role_info.rolcreaterole,
               role_info.rolbypassrls,
               role_info.rolreplication,
               role_info.rolinherit,
               role_info.rolcanlogin,
               EXISTS (
                   SELECT 1
                   FROM pg_auth_members AS membership
                   JOIN pg_roles AS member ON member.oid = membership.member
                   WHERE member.rolname = role_info.rolname
               ) AS has_membership
        FROM pg_roles AS role_info
        WHERE role_info.rolname = ANY($1::text[])
        """,
        names,
    )
    grant_query: str = await connection.fetchval(
        "SELECT format($1::text, $2::text)",
        "SELECT DISTINCT role_name FROM %I.role_queue_grants "
        "WHERE role_name = ANY($1::text[])",
        COMPUTE_QUEUE_SCHEMA,
    )
    managed = await connection.fetch(grant_query, names)
    managed_names = {str(row["role_name"]) for row in managed}
    configured = {role.name: role for role in roles}

    for row in existing:
        role_name = str(row["rolname"])
        if role_name in managed_names:
            continue
        profile = [
            label
            for column, label in (
                ("rolsuper", "SUPERUSER"),
                ("rolcreatedb", "CREATEDB"),
                ("rolcreaterole", "CREATEROLE"),
                ("rolbypassrls", "BYPASSRLS"),
                ("rolreplication", "REPLICATION"),
                ("rolinherit", "INHERIT"),
            )
            if row[column]
        ]
        if not row["rolcanlogin"]:
            profile.append("NOLOGIN")
        if row["has_membership"]:
            profile.append("role membership")
        if not profile:
            profile.append("ordinary login")
        raise ValueError(
            f"{configured[role_name].env_var}={role_name!r} names an "
            "unmanaged existing database role with "
            f"{', '.join(profile)}; refusing to alter it"
        )


async def _load_role_state(connection: asyncpg.Connection) -> dict[str, str]:
    """Create and read the owner-only record of roles managed by this module."""
    await _ddl(
        connection,
        "CREATE TABLE IF NOT EXISTS %I.%I ("
        "role_kind text PRIMARY KEY CHECK (role_kind = ANY("
        "ARRAY['producer', 'worker', 'purger']::text[])), "
        "role_name text NOT NULL UNIQUE"
        ")",
        COMPUTE_QUEUE_SCHEMA,
        _ROLE_STATE_TABLE,
    )
    await _ddl(
        connection,
        "REVOKE ALL PRIVILEGES ON %I.%I FROM PUBLIC",
        COMPUTE_QUEUE_SCHEMA,
        _ROLE_STATE_TABLE,
    )
    rows = await connection.fetch(
        f"SELECT role_kind, role_name FROM {COMPUTE_QUEUE_SCHEMA}.{_ROLE_STATE_TABLE}",  # noqa: S608
    )
    return {str(row["role_kind"]): str(row["role_name"]) for row in rows}


async def _retire_role(
    connection: asyncpg.Connection, role_kind: str, role: str
) -> None:
    """Remove every grant and the database role from an old configuration."""
    exists = await connection.fetchval(
        "SELECT 1 FROM pg_roles WHERE rolname = $1", role
    )
    if not exists:
        return

    # The policy's role list is a dependency on the role. Remove it before
    # DROP ROLE; the current purger provisioning recreates it for its new name.
    if role_kind == "purger":
        await _ddl(
            connection,
            "DROP POLICY IF EXISTS %I ON %I.%I",
            "compute_purger_terminal_delete",
            COMPUTE_QUEUE_SCHEMA,
            "jobs",
        )
    await _reset_role_security(connection, role)
    await _ddl(connection, "REVOKE ALL PRIVILEGES ON compute.jobs FROM %I", role)
    await _ddl(connection, "REVOKE ALL PRIVILEGES ON SCHEMA compute FROM %I", role)
    await revoke_role(connection, role=role, schema=COMPUTE_QUEUE_SCHEMA, drop=True)


async def _retire_previous_roles(
    connection: asyncpg.Connection,
    previous: dict[str, str],
    roles: tuple[QueueRole, ...],
) -> None:
    """Retire names removed from the last successful provisioning run."""
    current_names = {role.name for role in roles}
    for role_kind, role in previous.items():
        if role_kind in _ROLE_KINDS and role not in current_names:
            await _retire_role(connection, role_kind, role)


async def _save_role_state(
    connection: asyncpg.Connection, roles: tuple[QueueRole, ...]
) -> None:
    """Record the names only after all role provisioning has succeeded."""
    await connection.execute(
        f"DELETE FROM {COMPUTE_QUEUE_SCHEMA}.{_ROLE_STATE_TABLE}"  # noqa: S608
    )
    await connection.executemany(
        f"INSERT INTO {COMPUTE_QUEUE_SCHEMA}.{_ROLE_STATE_TABLE} "  # noqa: S608
        "(role_kind, role_name) VALUES ($1, $2)",
        ((kind, role.name) for kind, role in zip(_ROLE_KINDS, roles, strict=True)),
    )


async def provision_queue_roles(connection: asyncpg.Connection) -> None:
    """Create or repair every runtime role, scoped to COMPUTE_QUEUE."""
    _validate_compute_queue()
    roles = queue_roles()
    _validate_role_names(roles)
    previous = await _load_role_state(connection)
    await _validate_existing_role_names(connection, roles)
    await _retire_previous_roles(connection, previous, roles)

    for role in roles:
        if not role.password:
            raise RuntimeError(
                f"{role.env_var} must be set: it is the password for "
                f"the database role {role.name}."
            )
        await provision_role(
            connection,
            role=role.name,
            capabilities=role.capabilities,
            schema=COMPUTE_QUEUE_SCHEMA,
            # One queue, so the row-level-security scope is that queue rather
            # than '*'. A second queue would need a row here, not a code change.
            queues=(COMPUTE_QUEUE,),
            password=role.password,
        )
        await _reset_role_security(connection, role.name)
        if role.name == COMPUTE_WORKER_ROLE:
            # The pinned rqueue revision includes INSERT in CONSUME, although
            # a consumer only claims and transitions producer-created jobs.
            await _ddl(
                connection,
                "REVOKE INSERT ON %I.%I FROM %I",
                COMPUTE_QUEUE_SCHEMA,
                "jobs",
                role.name,
            )
        for table, privileges in role.extra_queue_privileges:
            await _ddl(
                connection,
                f"GRANT {privileges} ON %I.%I TO %I",
                COMPUTE_QUEUE_SCHEMA,
                table,
                role.name,
            )
        if role.name == COMPUTE_PURGER_ROLE:
            await _grant_purger_delete_policy(connection, role)
        await _grant_compute_access(connection, role)
        logger.info(
            "provisioned %s with %s on queue %s",
            role.name,
            ", ".join(capability.value for capability in role.capabilities),
            COMPUTE_QUEUE,
        )
    await _save_role_state(connection, roles)


async def _run() -> None:
    connection = await asyncpg.connect(COMPUTE_DATABASE_URL)
    try:
        async with connection.transaction():
            await provision_queue_roles(connection)
    finally:
        await connection.close()


def main() -> None:  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    main()
