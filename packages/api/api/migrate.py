"""Create the compute schema and provision the web database role.

Run this before applying the queue and web schemas. The command connects as the
database owner. The web role is a runtime-only role.
"""

import logging
from pathlib import Path

import psycopg
from psycopg import sql

from api.core.settings import (
    APP_DB_PASSWORD,
    APP_DB_ROLE,
    COMPUTE_DATABASE_URL,
)

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Serializes concurrent `tsdhn-compute-migrate` runs, such as two Compose stacks.
_MIGRATION_LOCK_ID = 0x7364686E


def install_compute_schema(
    conn: psycopg.Connection[tuple[str, ...]], migrations_dir: Path = MIGRATIONS_DIR
) -> list[str]:
    """Apply the numbered `*.sql` files that are not recorded yet, in name order.

    Returns the versions applied by this call. Each file runs in the caller's
    transaction, so a failure leaves the schema as it was.
    """
    conn.execute("SELECT pg_advisory_xact_lock(%s)", [_MIGRATION_LOCK_ID])
    conn.execute("CREATE SCHEMA IF NOT EXISTS compute")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS compute.schema_migrations ("
        "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    applied = {
        row[0] for row in conn.execute("SELECT version FROM compute.schema_migrations")
    }
    newly_applied = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.stem in applied:
            continue
        conn.execute(path.read_text())
        conn.execute(
            "INSERT INTO compute.schema_migrations (version) VALUES (%s)", [path.stem]
        )
        newly_applied.append(path.stem)
    return newly_applied


def transfer_web_ownership(
    conn: psycopg.Connection[tuple[str, ...]],
    web_role: str,
    migration_role: sql.Identifier,
) -> None:
    """Transfer the web role's tables, sequences, and `drizzle` schema to the owner."""
    objects = conn.execute(
        """
        SELECT n.nspname, c.relname, c.relkind
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('public', 'drizzle')
          AND c.relkind IN ('r', 'p', 'S')
          AND pg_get_userbyid(c.relowner) = %s
        """,
        [web_role],
    ).fetchall()
    for schema_name, name, kind in objects:
        object_type = "SEQUENCE" if kind == "S" else "TABLE"
        conn.execute(
            sql.SQL(
                "ALTER {object_type} {schema_name}.{name} OWNER TO {migration_role}"
            ).format(
                object_type=sql.SQL(object_type),
                schema_name=sql.Identifier(schema_name),
                name=sql.Identifier(name),
                migration_role=migration_role,
            )
        )

    drizzle_owner = conn.execute(
        """
        SELECT 1
        FROM pg_namespace
        WHERE nspname = 'drizzle' AND nspowner = %s::regrole
        """,
        [web_role],
    ).fetchone()
    if drizzle_owner:
        conn.execute(
            sql.SQL("ALTER SCHEMA drizzle OWNER TO {migration_role}").format(
                migration_role=migration_role
            )
        )
        conn.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA drizzle FROM {web_role}").format(
                web_role=sql.Identifier(web_role)
            )
        )
        conn.execute("REVOKE CREATE ON SCHEMA drizzle FROM PUBLIC")


def provision_web_role(conn: psycopg.Connection[tuple[str, ...]]) -> None:
    """Create the runtime web role with only its required data privileges."""
    if not APP_DB_PASSWORD:
        raise RuntimeError(
            "APP_DB_PASSWORD must be set: it is the password for the "
            f"web app's database role ({APP_DB_ROLE})."
        )

    role = sql.Identifier(APP_DB_ROLE)
    database = sql.Identifier(conn.info.dbname)
    migration_role = sql.Identifier(conn.info.user)
    exists = conn.execute(
        "SELECT 1 FROM pg_roles WHERE rolname = %s", [APP_DB_ROLE]
    ).fetchone()

    action = sql.SQL("ALTER ROLE") if exists else sql.SQL("CREATE ROLE")
    conn.execute(
        sql.SQL("{action} {role} LOGIN PASSWORD {password}").format(
            action=action, role=role, password=sql.Literal(APP_DB_PASSWORD)
        )
    )
    transfer_web_ownership(conn, APP_DB_ROLE, migration_role)

    # The web role is deliberately not a migration role. Rerunning provisioning
    # repairs these boundaries if the role was over-granted.
    for statement in (
        sql.SQL("REVOKE CREATE ON DATABASE {database} FROM {role}"),
        sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"),
        sql.SQL("REVOKE CREATE ON SCHEMA public FROM {role}"),
        sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {role}"),
        sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {role}"),
        sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA compute FROM {role}"),
        sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA compute FROM {role}"),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {migration_role} IN SCHEMA public "
            "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {role}"
        ),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {migration_role} IN SCHEMA public "
            "REVOKE USAGE, SELECT, UPDATE ON SEQUENCES FROM {role}"
        ),
        sql.SQL("REVOKE ALL PRIVILEGES ON compute.jobs FROM {role}"),
        sql.SQL("GRANT CONNECT ON DATABASE {database} TO {role}"),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {role}"),
        sql.SQL("GRANT USAGE ON SCHEMA compute TO {role}"),
        sql.SQL("GRANT SELECT ON compute.jobs TO {role}"),
    ):
        conn.execute(
            statement.format(
                role=role, database=database, migration_role=migration_role
            )
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    with psycopg.connect(COMPUTE_DATABASE_URL, connect_timeout=5) as conn:
        applied = install_compute_schema(conn)
        provision_web_role(conn)
        conn.commit()
    logger.info(
        "compute migrations applied: %s; role %s provisioned",
        ", ".join(applied) or "none pending",
        APP_DB_ROLE,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
