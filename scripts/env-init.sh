#!/usr/bin/env bash
# Create an env file from .env.example with a random value for every secret.
# Usage: scripts/env-init.sh [path]   (default: .env in the current directory)
#
# With --worker, write the env file of a worker host instead, from the main
# host's file. Run it on the main host and copy the result to the worker host.
# Usage: scripts/env-init.sh --worker [--from MAIN_ENV] [path]
#   MAIN_ENV defaults to /etc/tsdhn/prod.env and path to worker.env.
set -euo pipefail

worker=0
source_env=/etc/tsdhn/prod.env
args=()
while [ $# -gt 0 ]; do
    case "$1" in
        --worker) worker=1; shift ;;
        --from) source_env="${2:?--from needs a path}"; shift 2 ;;
        -*) echo "usage: $0 [path] | $0 --worker [--from MAIN_ENV] [path]" >&2; exit 2 ;;
        *) args+=("$1"); shift ;;
    esac
done
if [ "${#args[@]}" -gt 1 ]; then
    echo "usage: $0 [path] | $0 --worker [--from MAIN_ENV] [path]" >&2
    exit 2
fi

if [ "$worker" = 1 ]; then
    target="${args[0]:-worker.env}"
else
    target="${args[0]:-.env}"
fi
example="$(dirname "${BASH_SOURCE[0]}")/../.env.example"

if [ -e "$target" ] || [ -L "$target" ]; then
    echo "Refusing to overwrite existing $target" >&2
    exit 1
fi

umask 077
tmp_file="$(mktemp "$target.XXXXXX")"
trap 'rm -f "$tmp_file"' EXIT

if [ "$worker" = 1 ]; then
    if [ ! -r "$source_env" ]; then
        echo "Cannot read $source_env; pass --from" >&2
        exit 1
    fi

    value() {
        sed -n "s/^$1=//p" "$source_env" | tail -n 1
    }
    require() {
        if [ -z "$(value "$1")" ]; then
            echo "Set $1 in $source_env first: $2" >&2
            exit 1
        fi
    }

    require TSDHN_PRIVATE_ADDR "it is the address worker hosts reach PostgreSQL on"
    require API_IMAGE "worker hosts pull the same release"
    require COMPUTE_WORKER_PASSWORD "run scripts/env-init.sh to generate it"
    require TSDHN_S3_ACCESS_KEY "it is the key of the output bucket"
    require TSDHN_S3_SECRET_KEY "it is the secret of the output bucket"

    # An external store is reached at its own address. The bundled storage is
    # published on the private address, which compose.private.yml opens. The
    # fallbacks are the defaults of compose.prod.yml, so both hosts sign and
    # connect the same way.
    s3_endpoint="$(value TSDHN_S3_ENDPOINT)"
    s3_endpoint="${s3_endpoint:-$(value TSDHN_PRIVATE_ADDR):9000}"
    s3_secure="$(value TSDHN_S3_SECURE)"
    s3_region="$(value TSDHN_S3_REGION)"

    {
        echo "# Worker host. Written by scripts/env-init.sh --worker."
        echo "# Set TSDHN_WORKER_CONCURRENCY and TSDHN_NUMBA_THREADS for this host."
        echo "API_IMAGE=$(value API_IMAGE)"
        echo "COMPUTE_RUNTIME_DATABASE_URL=postgresql://$(value TSDHN_PRIVATE_ADDR):5432/tsdhn"
        echo "TSDHN_S3_ENDPOINT=$s3_endpoint"
        echo "TSDHN_S3_SECURE=${s3_secure:-false}"
        echo "TSDHN_S3_REGION=${s3_region:-us-east-1}"
        for name in COMPUTE_QUEUE COMPUTE_QUEUE_SCHEMA COMPUTE_WORKER_ROLE \
            COMPUTE_WORKER_PASSWORD TSDHN_S3_ACCESS_KEY TSDHN_S3_SECRET_KEY \
            TSDHN_S3_BUCKET; do
            if [ -n "$(value "$name")" ]; then
                echo "$name=$(value "$name")"
            fi
        done
        echo "TSDHN_WORKER_CONCURRENCY=1"
        echo "TSDHN_NUMBA_THREADS="
    } > "$tmp_file"

    chmod 600 "$tmp_file"
    mv "$tmp_file" "$target"
    trap - EXIT
    echo "Created $target from $source_env (mode 600)."
    exit 0
fi

secrets=" COMPUTE_API_TOKEN BETTER_AUTH_SECRET POSTGRES_PASSWORD APP_DB_PASSWORD \
COMPUTE_PRODUCER_PASSWORD COMPUTE_WORKER_PASSWORD COMPUTE_PURGER_PASSWORD \
TSDHN_S3_ACCESS_KEY TSDHN_S3_SECRET_KEY BACKUP_PASSWORD "

while IFS= read -r line; do
    name="${line%%=*}"
    if [ "$line" = "$name=" ] && [[ "$secrets" == *" $name "* ]]; then
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
