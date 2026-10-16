#!/usr/bin/env bash
set -euo pipefail

# Fail when a Dockerfile ARG default differs from the version .tool-versions pins.
root="$(dirname "$0")/.."
status=0

check() {
    local dockerfile=$1 arg=$2 tool=$3 default pinned
    default="$(sed -n "s/^ARG ${arg}=//p" "$root/$dockerfile")"
    pinned="$("$root/scripts/tool-version.sh" "$tool")"
    if [ "$default" != "$pinned" ]; then
        echo "$dockerfile: ARG $arg defaults to '${default}', .tool-versions pins $tool $pinned" >&2
        status=1
    fi
}

check deploy/api.Dockerfile UV_VERSION uv
check deploy/web.Dockerfile BUN_VERSION bun
exit "$status"
