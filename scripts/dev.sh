#!/usr/bin/env bash
set -euo pipefail

# Start the local stack and wait for the web app and API to answer.
cd "$(dirname "$0")/.."

if [ ! -e .env ]; then
    mise run init:env
fi

. scripts/dev-engine.sh
config_dir="$(mktemp -d "${TMPDIR:-/tmp}/tsdhn-dev.XXXXXX")"
docker_config="$config_dir/docker"
buildx_config="$config_dir/buildx"
trap 'rm -rf "$config_dir"' EXIT
mkdir -p "$docker_config" "$buildx_config"
UV_VERSION="$(mise current uv)" \
BUN_VERSION="$(mise current bun)" \
DOCKER_CONFIG="$docker_config" BUILDX_CONFIG="$buildx_config" \
docker compose --profile web up -d --build

for _ in $(seq 1 60); do
    if curl -fsS http://localhost:8000/api/v1/health >/dev/null 2>&1 \
        && curl -fsS http://localhost:3000 >/dev/null; then
        echo "Web: http://localhost:3000"
        echo "API docs: http://localhost:8000/api-docs"
        echo "Storage console: http://localhost:9001"
        echo "Sign up at /signup to create a local account (email plus a password of at least 8 characters; no email verification)."
        exit 0
    fi
    sleep 2
done

echo "The local stack did not become healthy within 120 seconds." >&2
DOCKER_CONFIG="$docker_config" docker compose --profile web ps >&2 || true
exit 1
