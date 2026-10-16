#!/usr/bin/env bash
# Create an env file from .env.example with a random value for every secret.
# Usage: scripts/env-init.sh [path]   (default: .env in the current directory)
set -euo pipefail

target="${1:-.env}"
example="$(dirname "${BASH_SOURCE[0]}")/../.env.example"

if [ -e "$target" ] || [ -L "$target" ]; then
    echo "Refusing to overwrite existing $target" >&2
    exit 1
fi

secrets=" COMPUTE_API_TOKEN BETTER_AUTH_SECRET POSTGRES_PASSWORD APP_DB_PASSWORD \
COMPUTE_PRODUCER_PASSWORD COMPUTE_WORKER_PASSWORD COMPUTE_PURGER_PASSWORD \
TSDHN_S3_ACCESS_KEY TSDHN_S3_SECRET_KEY "

umask 077
tmp_file="$(mktemp "$target.XXXXXX")"
trap 'rm -f "$tmp_file"' EXIT

while IFS= read -r line; do
    name="${line%%=*}"
    if [ "$line" = "$name=" ] && [[ "$secrets" == *" $name "* ]]; then
        # An S3 access key is 20 characters and a secret key is 40.
        case "$name" in
            TSDHN_S3_ACCESS_KEY) line="$name=$(openssl rand -hex 10)" ;;
            TSDHN_S3_SECRET_KEY) line="$name=$(openssl rand -hex 20)" ;;
            *) line="$name=$(openssl rand -hex 32)" ;;
        esac
    fi
    printf '%s\n' "$line"
done < "$example" > "$tmp_file"

chmod 600 "$tmp_file"
mv "$tmp_file" "$target"
trap - EXIT
echo "Created $target with generated secrets (mode 600)."
