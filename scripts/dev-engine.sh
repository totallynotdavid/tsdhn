#!/usr/bin/env bash

runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
socket="$runtime_dir/podman/podman.sock"
export DOCKER_HOST="unix://$socket"

if [ ! -S "$socket" ]; then
    systemctl --user start podman.socket >/dev/null 2>&1 || true
fi

if ! docker version >/dev/null 2>&1; then
    echo "Podman engine unavailable; run systemctl --user start podman.socket and retry." >&2
    return 1 2>/dev/null || exit 1
fi
