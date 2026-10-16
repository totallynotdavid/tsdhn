#!/usr/bin/env bash
set -euo pipefail

# Print each local stack container's state and health.
cd "$(dirname "$0")/.."

. scripts/dev-engine.sh
docker compose --profile web ps -a
for container in $(docker compose --profile web ps -aq); do
    name=$(docker inspect --format '{{.Name}}' "$container")
    state=$(docker inspect --format '{{.State.Status}}' "$container")
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}not-configured{{end}}' "$container")
    printf '%s state=%s health=%s\n' "$name" "$state" "$health"
done
