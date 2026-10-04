#!/usr/bin/env bash
set -euo pipefail

# These tests own this project-local cluster and never accept a production URL.
pg_port="${TSDHN_PG_PORT:-5432}"
base_url="postgresql://tsdhn:tsdhn@127.0.0.1:${pg_port}/tsdhn"
database_name="tsdhn_integration_$(date +%s)_$$"
app_role="${database_name}_role"
app_password="tsdhn-web-test-password"
data_dir="$PWD/.data/postgres"
server_started=0
database_created=0
queue_schema="${COMPUTE_QUEUE_SCHEMA:-task_queue}"
queue_name="${COMPUTE_QUEUE:-simulations}"

# Roles are cluster-wide, so each disposable database gets unique role names.
producer_role="${database_name}_producer"
worker_role="${database_name}_worker"
purger_role="${database_name}_purger"
queue_password="tsdhn-queue-test-password"

case "${1:-}" in
    "") coverage=0 ;;
    --coverage) coverage=1 ;;
    *) echo "usage: $0 [--coverage]" >&2; exit 2 ;;
esac

cleanup() {
    status=$?
    if [ "$database_created" -eq 1 ]; then
        uv run python -m scripts.database drop \
            --base-url "$base_url" \
            --name "$database_name" \
            --role "$app_role" \
            --role "$producer_role" \
            --role "$worker_role" \
            --role "$purger_role" >/dev/null || status=$?
    fi
    if [ "$server_started" -eq 1 ]; then
        mise run db:stop >/dev/null || status=$?
    fi
    return "$status"
}
trap cleanup EXIT

# Skip database startup if COMPUTE_DATABASE_URL is set (e.g., by CI with service container)
if [ -z "${COMPUTE_DATABASE_URL:-}" ]; then
    project_server_running=0
    if mise x postgres -- pg_ctl -D "$data_dir" status >/dev/null 2>&1; then
        project_server_running=1
    fi
    if ! mise run db:start; then
        if [ "$project_server_running" -eq 0 ] && mise x postgres -- pg_ctl -D "$data_dir" status >/dev/null 2>&1; then
            server_started=1
        fi
        exit 1
    fi
    if [ "$project_server_running" -eq 0 ]; then
        server_started=1
    fi
fi

admin_url="$(
    uv run python -m scripts.database create \
        --base-url "$base_url" \
        --name "$database_name"
)"
database_created=1
app_url="$(
    uv run python -m scripts.database url \
        --base-url "$admin_url" \
        --name "$database_name" \
        --user "$app_role" \
        --password "$app_password"
)"

COMPUTE_DATABASE_URL="$admin_url" \
APP_DB_ROLE="$app_role" \
APP_DB_PASSWORD="$app_password" \
uv run tsdhn-compute-migrate

uv run rqueue --database-url "$admin_url" --schema "$queue_schema" migrate

COMPUTE_DATABASE_URL="$admin_url" \
COMPUTE_QUEUE="$queue_name" \
COMPUTE_QUEUE_SCHEMA="$queue_schema" \
COMPUTE_PRODUCER_ROLE="$producer_role" \
COMPUTE_PRODUCER_PASSWORD="$queue_password" \
COMPUTE_WORKER_ROLE="$worker_role" \
COMPUTE_WORKER_PASSWORD="$queue_password" \
COMPUTE_PURGER_ROLE="$purger_role" \
COMPUTE_PURGER_PASSWORD="$queue_password" \
uv run tsdhn-queue-grants

# Schema changes run with the database-owner connection. The app role below
# is intentionally limited to runtime DML and compute-state reads.
DATABASE_URL="$admin_url" bun --filter web db:migrate

COMPUTE_DATABASE_URL="$admin_url" \
APP_DB_ROLE="$app_role" \
uv run tsdhn-web-grants

if [[ "$coverage" == "1" ]]; then
    uv run coverage run -m pytest -m integration packages/api/tests
else
    uv run pytest -m integration packages/api/tests
fi

DATABASE_URL="$app_url" \
    bun --filter web test:integration
