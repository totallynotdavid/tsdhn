#!/usr/bin/env bash
set -euo pipefail

# Print the version .tool-versions pins for a tool: scripts/tool-version.sh uv
awk -v tool="${1:?usage: tool-version.sh <tool>}" '
    $1 == tool { print $2; found = 1 }
    END { exit !found }
' "$(dirname "$0")/../.tool-versions"
