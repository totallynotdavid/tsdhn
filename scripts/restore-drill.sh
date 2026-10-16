#!/usr/bin/env bash
# Restore the latest backup into a disposable copy of the production stack and
# read a restored job through the API. See "Recovery test" in docs/deploy.md.
# Usage: scripts/restore-drill.sh [--env-file FILE] [--snapshot ID] [--keep]
# The copy is its own Compose project and only reads the backup repository.
# --keep leaves it running. The script prints the command that removes it.
set -euo pipefail

env_file=/etc/tsdhn/prod.env
snapshot=latest
keep=0
while [ $# -gt 0 ]; do
    case "$1" in
        --env-file) env_file="${2:?--env-file needs a path}"; shift 2 ;;
        --snapshot) snapshot="${2:?--snapshot needs an id}"; shift 2 ;;
        --keep) keep=1; shift ;;
        *) echo "usage: $0 [--env-file FILE] [--snapshot ID] [--keep]" >&2; exit 2 ;;
    esac
done

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project="tsdhn-drill-$(date +%s)"
compose=(docker compose -p "$project" --env-file "$env_file" -f "$root/deploy/compose.prod.yml")

if [ ! -r "$env_file" ]; then
    echo "cannot read $env_file; pass --env-file" >&2
    exit 2
fi
if ! command -v jq >/dev/null; then
    echo "jq is required to read the API's answers" >&2
    exit 2
fi

# The copy restores into its own bundled object store, even when production
# keeps outputs in an external bucket such as R2. Exported values win over the
# env file.
export TSDHN_S3_ENDPOINT=storage:9000 TSDHN_S3_SECURE=false \
    TSDHN_S3_REGION=us-east-1

cleanup() {
    if [ "$keep" = 1 ]; then
        echo "kept the restored stack; remove it with:"
        printf '  %q ' "${compose[@]}"
        echo "--profile restore down -v"
    else
        "${compose[@]}" --profile restore down -v --remove-orphans >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

psql_restored() {
    "${compose[@]}" exec -T postgres psql -U tsdhn -d tsdhn -Atc "$1"
}

# Run inside the API container, which holds the token and reaches the object
# store by the name the download URLs carry.
api_get() {
    "${compose[@]}" exec -T api sh -c \
        'curl -fsS -L -H "Authorization: Bearer $COMPUTE_API_TOKEN" "$@"' sh "$@"
}

echo "== starting an empty PostgreSQL and object store ($project)"
"${compose[@]}" up -d --wait postgres storage

echo "== restoring snapshot $snapshot"
"${compose[@]}" --profile restore run --rm restore restore "$snapshot"

# Migrations and role grants run after the restore, as they do on every start.
echo "== starting the API on the restored data"
"${compose[@]}" up -d --wait api

job="$(psql_restored "SELECT simulation_id FROM compute.jobs
    WHERE status = 'completed' AND outputs_expired_at IS NULL
    ORDER BY finished_at DESC LIMIT 1")"
if [ -z "$job" ]; then
    echo "the restored database has no completed job with its outputs" >&2
    exit 1
fi

echo "== job $job"
api_get "http://127.0.0.1:8000/api/v1/jobs/$job" | jq '{status, step, finished_at, outputs}'

name="$(api_get "http://127.0.0.1:8000/api/v1/jobs/$job/outputs" | jq -er '.outputs[0].name')"
bytes="$(api_get "http://127.0.0.1:8000/api/v1/jobs/$job/outputs/$name" | wc -c)"
echo "== output $name: $bytes bytes"
if [ "$bytes" -le 0 ]; then
    echo "the restored output is empty" >&2
    exit 1
fi

echo "== restore drill passed"
