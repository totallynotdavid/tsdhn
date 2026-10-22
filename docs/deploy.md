# Deploy

The repository includes two Docker Compose stacks for the API, the worker,
PostgreSQL, RustFS and the web app: a local stack for development
([`docker-compose.yml`](../docker-compose.yml)) and a production stack
([`deploy/compose.prod.yml`](../deploy/compose.prod.yml)). Named volumes hold
PostgreSQL data, object storage data and worker workspaces. Both stacks pin the
same RustFS image version.

[Local stack](#local-stack) covers development. [Production](#production) covers
the stack that runs behind a Cloudflare Tunnel.
[Add a worker host](#add-a-worker-host) covers more machines that run
simulations.

## Settings

The API and worker read these environment variables. Defaults apply when a
variable is unset.

| Variable                                                            | Default                                          | Meaning                                                             |
| ------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------- |
| `COMPUTE_DATABASE_URL`                                              | `postgresql://tsdhn:tsdhn@localhost:5432/tsdhn`  | Schema-owner URL, used for migrations and provisioning              |
| `COMPUTE_RUNTIME_DATABASE_URL`                                      | `COMPUTE_DATABASE_URL`                           | Passwordless URL that runtime roles connect through                 |
| `TSDHN_PG_PORT`                                                     | `5432`                                           | Port in the default `COMPUTE_DATABASE_URL`                          |
| `COMPUTE_QUEUE`, `COMPUTE_QUEUE_SCHEMA`                             | `simulations`, `task_queue`                      | Queue name and the schema rqueue owns                               |
| `COMPUTE_PRODUCER_ROLE`, `_WORKER_ROLE`, `_PURGER_ROLE`             | `tsdhn_producer`, `tsdhn_worker`, `tsdhn_purger` | Runtime role names                                                  |
| `COMPUTE_PRODUCER_PASSWORD`, `_WORKER_PASSWORD`, `_PURGER_PASSWORD` | none (required)                                  | Runtime role passwords                                              |
| `APP_DB_ROLE`, `APP_DB_PASSWORD`                                    | `tsdhn_app`, none                                | Web runtime role                                                    |
| `TSDHN_DB_POOL_MIN_SIZE`, `TSDHN_DB_POOL_MAX_SIZE`                  | `0`, `10`                                        | Connection pool bounds                                              |
| `TSDHN_JOBS_DIR`                                                    | `jobs`                                           | Directory that holds one workspace per simulation                   |
| `TSDHN_WORKER_CONCURRENCY`                                          | `1`                                              | Simulations a worker runs at once                                   |
| `TSDHN_WORKER_LEASE_SECONDS`                                        | `60`                                             | Queue lease length                                                  |
| `TSDHN_WORKER_ID`                                                   | empty                                            | Worker name in queue records                                        |
| `TSDHN_WORKER_HEARTBEAT_FILE`                                       | empty                                            | File the worker touches every 10 seconds while the database answers |
| `TSDHN_NUMBA_THREADS`                                               | all visible CPUs                                 | Threads for the solver                                              |
| `TSDHN_LOG_LEVEL`                                                   | `INFO`                                           | Log level                                                           |
| `TSDHN_S3_ENDPOINT`                                                 | `localhost:9000`                                 | S3 address the API uploads to and signs download URLs for           |
| `TSDHN_S3_ACCESS_KEY`, `TSDHN_S3_SECRET_KEY`                        | `tsdhn-local`, `tsdhn-local-secret`              | S3 credentials                                                      |
| `TSDHN_S3_BUCKET`, `TSDHN_S3_SECURE`                                | `tsdhn-results`, `false`                         | Bucket name and TLS                                                 |
| `TSDHN_S3_REGION`                                                   | `us-east-1`                                      | Region that signs download URLs; `auto` for Cloudflare R2           |
| `TSDHN_RETENTION_ENABLED`                                           | `true`                                           | `false` turns off the output expiry and queue purge on this host    |
| `TSDHN_OUTPUT_URL_TTL_SECONDS`                                      | `900`                                            | Lifetime of a download URL                                          |
| `TSDHN_OUTPUT_RETENTION_DAYS`                                       | `90`                                             | Days a completed job keeps its output files; `0` keeps them         |
| `TSDHN_SSE_MAX_DURATION_SECONDS`                                    | `1800`                                           | Longest progress stream                                             |
| `COMPUTE_API_TOKEN`                                                 | none (required)                                  | Bearer token for every route except health and version              |
| `TSDHN_ALLOWED_ORIGINS`                                             | empty                                            | Comma-separated origins that may call the API directly              |
| `TSDHN_HOST`, `TSDHN_PORT`                                          | `127.0.0.1`, `8000`                              | Address `tsdhn-api` listens on                                      |

Retry limits, the 24 hour workspace lifetime and the seven day queue retention
are fixed in the code. [Jobs](jobs.md) states them, and what a user sees when
the output retention has deleted a job's files.

The web app downloads each output from the address in the signed URL the API
returns and streams it to the browser. `TSDHN_S3_ENDPOINT` must therefore name
an address the web app reaches: `storage:9000` for the bundled RustFS, or the S3
host of an external store such as [Cloudflare R2](#object-storage-on-r2).

## Local stack

The local stack builds its images, runs over the Podman socket and publishes the
RustFS console.

### Configure

Create the local environment before you start the stack (also done by `dev`):

```sh
mise run init:env
```

`env-init` refuses to overwrite an existing `.env`, generates the ten required
secrets and writes the file with mode 600: the compute API token, the Better
Auth secret, the PostgreSQL password, the web role password, the three
queue-role passwords, the two object storage keys and the backup password. The
local stack ignores the PostgreSQL password and uses a fixed one, and does not
run backups. See [Database](database.md#compute-roles) for the roles.

The example uses queue `simulations` in schema `task_queue`. Compose sets the
runtime database endpoint and the S3 endpoints for its containers itself.

### Start

Install the pinned tools, then start the complete local stack:

```sh
mise install
mise run dev
```

`dev` creates `.env` when it is missing, checks the Podman socket, builds local
images, starts every service in detached mode, applies migrations and waits for
the API and web health checks. It prints the addresses when they are ready. Open
`/signup` to create a local account with an email and a password of at least 8
characters. Local accounts do not need email verification.

| Address                          | Service                 |
| -------------------------------- | ----------------------- |
| <http://localhost:3000>          | Web app                 |
| <http://localhost:8000/api-docs> | Compute API, OpenAPI UI |
| <http://localhost:9001>          | RustFS storage console  |

The compute API serves its routes under `/api/v1`. The health and version routes
are public. The other routes need `COMPUTE_API_TOKEN`.

### Inspect and stop

Follow the service logs:

```sh
mise run dev:logs
```

Show each container's state and configured health status:

```sh
mise run dev:status
```

Stop the containers and keep the named volumes:

```sh
mise run dev:down
```

`dev:down` keeps the named volumes. The database and storage are disposable, so
wipe the containers, network and volumes when resetting the stack. The command
uses the same engine socket setup as the mise tasks:

```sh
. scripts/dev-engine.sh && docker compose --profile web down -v
```

## Production

[`deploy/compose.prod.yml`](../deploy/compose.prod.yml) runs the stack on one
host: the main host. It builds nothing: it pulls the API, web and backup images
you name. The Cloudflare Tunnel carries the web route to the Worker. The only
traffic that leaves the host besides the tunnel is the daily backup to an
S3-compatible bucket ([Backup and restore](#backup-and-restore)) and the traffic
to an external object store. [Add a worker host](#add-a-worker-host) runs
simulations on more machines.

### Networks and ports

| Network   | Members                                                 | Reach                                              |
| --------- | ------------------------------------------------------- | -------------------------------------------------- |
| `backend` | PostgreSQL, storage, API, worker, one-shot jobs and web | Internal: no route to the internet                 |
| `edge`    | web and `cloudflared`                                   | Outbound to Cloudflare                             |
| `offsite` | API, worker, `backup` and `restore`                     | Outbound to object storage and the backup bucket   |
| `private` | PostgreSQL, with `compose.private.yml` only             | Carries the port that worker hosts connect through |

Members of `backend` reach each other and nothing else. Only web also joins
`edge`, so `cloudflared` reaches web and no other service. The API and the
worker join `offsite` to reach an external object store. The backup services
join `backend` to read PostgreSQL and storage and `offsite` to reach the bucket.

Only web publishes a port, on `127.0.0.1:${TSDHN_WEB_PORT}` for checks from the
host. Storage and the API publish nothing, and the RustFS console is off.
PostgreSQL publishes a port on `TSDHN_PRIVATE_ADDR` once you
[add a worker host](#add-a-worker-host), and nothing before. Web proxies the
progress stream and the output downloads, so the API and storage need no public
address.

### Images

`API_IMAGE`, `WEB_IMAGE` and `BACKUP_IMAGE` are full image references with no
default. Name a release tag or a digest, never a branch tag. Print the digest of
a tag:

```sh
docker buildx imagetools inspect ghcr.io/totallynotdavid/tsdhn-api:v0.0.1
```

Set the reference to `ghcr.io/totallynotdavid/tsdhn-api@sha256:<digest>` to pin
it. The release workflow publishes `tsdhn-api`, `tsdhn-web`, `tsdhn-backup` and
`tsdhn-toolchain` to GHCR.

The API image contains the TTT SDK, and its licence forbids distributing the SDK
([Licence](#licence)). Keep the `tsdhn-api` and `tsdhn-toolchain` packages
private, and sign in on the host before you pull:

```sh
docker login ghcr.io
```

### Configure

Secrets live in one file outside the repository, readable by root only. Create
it from `.env.example` with generated secrets:

```sh
sudo install -d -m 700 /etc/tsdhn
sudo scripts/env-init.sh /etc/tsdhn/prod.env
sudo "$EDITOR" /etc/tsdhn/prod.env
```

Edit these values in the production section and above it:

| Variable                  | Value                                                              |
| ------------------------- | ------------------------------------------------------------------ |
| `ORIGIN`                  | `https://tsdhn.caefisica.workers.dev`                              |
| `API_IMAGE`               | API image reference                                                |
| `WEB_IMAGE`               | Web image reference                                                |
| `TUNNEL_TOKEN`            | Token of the Cloudflare tunnel                                     |
| `TSDHN_WEB_PORT`          | Loopback port for host checks, `3000` by default                   |
| `BACKUP_IMAGE`            | Backup image reference                                             |
| `BACKUP_REPOSITORY`       | restic repository on the bucket, `s3:https://HOST/BUCKET[/PREFIX]` |
| `BACKUP_S3_ACCESS_KEY`    | Access key of the bucket, not of the storage service               |
| `BACKUP_S3_SECRET_KEY`    | Secret key of the bucket                                           |
| `BACKUP_INTERVAL_SECONDS` | Seconds between backups, `86400` by default                        |

`env-init` generates `BACKUP_PASSWORD`, which encrypts every backup.
[Backup and restore](#backup-and-restore) says how to keep it. The worker reads
`TSDHN_OUTPUT_RETENTION_DAYS` from the same file ([Settings](#settings)).

Compose reads the file in the CLI, so run every command with `sudo` and name it:

```sh
alias tsdhn-prod='sudo docker compose --env-file /etc/tsdhn/prod.env -f deploy/compose.prod.yml'
```

Compose stops with the name of any missing required value.

### Cloudflare edge route

The public route is the `tsdhn` Worker, the `tsdhn-web` Workers VPC service and
the `tsdhn` tunnel. From the web container outward, the route is:

```text
web:3000 -> tsdhn tunnel -> tsdhn-web VPC service -> tsdhn Worker
```

Requests enter that route in the opposite direction. The tunnel has no public
hostname. `cloudflared` joins the `edge` network, where `web` resolves, and the
VPC service reaches that container through the tunnel.

The Worker source and its VPC binding live in
[`deploy/edge/src/index.ts`](../deploy/edge/src/index.ts) and
[`deploy/edge/cloudflare.config.ts`](../deploy/edge/cloudflare.config.ts).
Deploy it from that directory:

```sh
cd deploy/edge
bunx cf deploy
```

The Worker keeps the public workers.dev host and forwards the request to the VPC
binding over HTTP. A VPC service that accepts only HTTP refuses an HTTPS URL, so
the Worker changes the forwarded URL's scheme to `http:` and sets
`x-forwarded-proto: https` for the web app. `ORIGIN` must be the Worker's
workers.dev URL so origin checks use the public address.

The progress stream stays open for up to `TSDHN_SSE_MAX_DURATION_SECONDS`
(1800). Inside the stack nothing closes it early: the API sends a `: keepalive`
comment every 20 seconds and web relays the stream with
`Content-Type: text/event-stream`.

Cloudflare can still end a long-lived connection. Its documentation says that
stopping `cloudflared`, which an update or a configuration change does, drops
requests in flight, and that a proxied connection can be interrupted at
Cloudflare. A stream cut this way ends before the job does. The page shows the
job's state when it is reloaded. Quick Tunnels do not support server-sent
events, so use a named tunnel.

### Start, update and stop

```sh
tsdhn-prod pull
tsdhn-prod up -d
tsdhn-prod ps
```

`up` waits for each dependency: PostgreSQL and the bundled storage are healthy,
the migrations and role grants have completed, the API is healthy, then web,
then `cloudflared`. To deploy another release, change `API_IMAGE` and
`WEB_IMAGE` and run the three commands again. Stop the stack and keep its
volumes:

```sh
tsdhn-prod down
```

Add `-v` to delete the volumes too.

Check the site from the host through the loopback port. Web derives its own
origin from the `Host` header and treats requests as `https`, so a form post
over plain HTTP needs an `Origin` header with the `https` scheme:

```sh
curl -fsS http://127.0.0.1:3000/health
curl -sS -H 'Origin: https://127.0.0.1:3000' --data-urlencode name=you \
  --data-urlencode email=you@example.org --data-urlencode password=change-me-now \
  http://127.0.0.1:3000/signup
```

Through the tunnel the browser sends the public origin, which matches.

### Health checks

| Service       | Check                                                         |
| ------------- | ------------------------------------------------------------- |
| `postgres`    | `pg_isready`                                                  |
| `storage`     | `GET /health` (bundled storage only)                          |
| `api`         | `GET /api/v1/health` returns 200                              |
| `worker`      | Heartbeat file touched less than 60 seconds ago               |
| `web`         | `GET /health` returns 200                                     |
| `cloudflared` | `cloudflared tunnel ready` reports a connection to Cloudflare |
| `backup`      | Last successful backup less than two intervals ago            |

[Architecture](architecture.md#health-signals) defines what each signal means,
including the states of the worker's heartbeat file. `backup` has one hour to
finish its first run before a missing file counts as unhealthy.

### Object storage on R2

Outputs go to the bundled RustFS unless you name an external S3-compatible
store. [Cloudflare R2](https://developers.cloudflare.com/r2/) is the store to
use with worker hosts: they upload to it directly, and downloads cost no egress
fee.

1. In the Cloudflare dashboard, open **Storage & databases > R2 > Overview**.
   Create a bucket named `tsdhn-results`.
2. Under **API Tokens**, select **Manage**, then **Create Account API token**.
   Choose the permission **Object Read & Write**, select **Apply to specific
   buckets only** and pick that bucket. Select **Create API Token**.
3. Copy the **Access Key ID** and the **Secret Access Key**. The dashboard shows
   the secret once. Copy the S3 endpoint from the same page. It reads
   `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.
4. In `/etc/tsdhn/prod.env`, set the keys and the endpoint without `https://`:

   ```sh
   TSDHN_S3_ENDPOINT=<ACCOUNT_ID>.r2.cloudflarestorage.com
   TSDHN_S3_SECURE=true
   TSDHN_S3_REGION=auto
   TSDHN_S3_ACCESS_KEY=<Access Key ID>
   TSDHN_S3_SECRET_KEY=<Secret Access Key>
   ```

5. Add [`compose.external-storage.yml`](../deploy/compose.external-storage.yml)
   last in the `tsdhn-prod` alias. It removes the bundled RustFS and every wait
   for it. Without it the stack still starts RustFS next to R2:

   ```sh
   alias tsdhn-prod='sudo docker compose --env-file /etc/tsdhn/prod.env -f deploy/compose.prod.yml -f deploy/compose.external-storage.yml'
   ```

6. Apply the change and read the health body. `storage_connected` must be
   `true`. `--remove-orphans` stops and removes the old RustFS container; its
   data stays in the `storage-data` volume:

   ```sh
   tsdhn-prod up -d --remove-orphans
   tsdhn-prod exec api curl -fsS http://127.0.0.1:8000/api/v1/health
   ```

`TSDHN_S3_REGION=auto` is the region R2 signs for. The API signs each download
URL with the endpoint, the region and the secret key. A plain `curl` of the URL
downloads the file until `TSDHN_OUTPUT_URL_TTL_SECONDS` pass. A key limited to
one bucket may not look the bucket up. The API reads that refusal as "the bucket
exists" and any other failure as "storage is down".

Objects written to RustFS stay in the `storage-data` volume. Copy them into the
new bucket before you switch, or the jobs that list them point at files the new
bucket does not hold.

### Add a worker host

One main host runs web, the API, PostgreSQL, the backup and the tunnel. Any
number of worker hosts run only the worker. A worker host pulls the API image
that the main host runs, claims jobs from PostgreSQL over a private network and
uploads outputs to the object store. It builds nothing and keeps no data that
the stack needs.

The signal to add a host is the age of the oldest queued job. Read it on the
main host:

```sh
tsdhn-prod exec api curl -fsS http://127.0.0.1:8000/api/v1/health
```

```json
{
  "status": "healthy",
  "timestamp": "2026-10-16T21:35:16.583662+00:00",
  "database_connected": true,
  "storage_connected": true,
  "oldest_queued_age_seconds": 23.0
}
```

`oldest_queued_age_seconds` is how long the job that has waited longest has been
claimable. It is `0.0` when no job waits. It never changes the status. A
simulation takes about 13 minutes ([Reference run](#reference-run)), so an age
that stays above that means every worker is busy: add a host.

#### Prepare the main host

1. Join the main host and the worker host to one private network. With
   [Tailscale](https://tailscale.com/kb/1347/installation), install it on both
   hosts and run `sudo tailscale up`. With WireGuard, give each host an address
   in a subnet that only these hosts share. Print the main host's address:

   ```sh
   tailscale ip -4
   ```

2. Keep the outputs in a store that worker hosts reach. Use
   [R2](#object-storage-on-r2). With the bundled RustFS, leave
   `TSDHN_S3_ENDPOINT` unset: the worker env points at the main host's private
   address, where the stack publishes RustFS.
3. In `/etc/tsdhn/prod.env`, set the address and the network that workers
   connect from. `100.64.0.0/10` is the Tailscale range and the default. Use the
   WireGuard subnet otherwise:

   ```sh
   TSDHN_PRIVATE_ADDR=<address from step 1>
   TSDHN_PRIVATE_CIDR=100.64.0.0/10
   ```

4. Name `compose.private.yml` in the command from now on. It publishes
   PostgreSQL, and the bundled storage when it runs, on `TSDHN_PRIVATE_ADDR` and
   nowhere else. A stack that does not name the file publishes nothing. If the
   alias also names `compose.external-storage.yml`, keep that file last:

   ```sh
   alias tsdhn-prod='sudo docker compose --env-file /etc/tsdhn/prod.env -f deploy/compose.prod.yml -f deploy/compose.private.yml'
   tsdhn-prod up -d
   tsdhn-prod ps postgres
   ```

   `ps` lists `<address>:5432->5432/tcp`.

PostgreSQL accepts the `tsdhn_worker` role on the database `tsdhn` from
`TSDHN_PRIVATE_CIDR` with a `scram-sha-256` password, and the other containers
of the stack. It rejects every other connection. PostgreSQL does not use TLS:
the private network encrypts the traffic. PostgreSQL reads the rule at start.
After you change `TSDHN_PRIVATE_CIDR`, recreate it:

```sh
tsdhn-prod up -d --force-recreate postgres
```

#### Prepare the worker env

Generate the worker env on the main host. It holds the worker role password, the
object store keys, the image and the database address, and none of the other
secrets:

```sh
sudo scripts/env-init.sh --worker worker.env
```

Copy it to the worker host, and delete the copy on the main host. Copy
[`deploy/compose.worker.yml`](../deploy/compose.worker.yml) of the same release
next to it:

```sh
sudo cat worker.env | ssh admin@worker-host 'sudo install -D -m 600 /dev/stdin /etc/tsdhn/worker.env'
scp deploy/compose.worker.yml admin@worker-host:compose.worker.yml
ssh admin@worker-host 'sudo install -m 644 compose.worker.yml /etc/tsdhn/compose.worker.yml && rm compose.worker.yml'
sudo rm worker.env
```

#### Set up the worker host

1. Install Docker Engine with the Compose plugin from
   [docs.docker.com](https://docs.docker.com/engine/install/). Join the private
   network as above.
2. Sign in to GHCR with a token that can read packages. The `tsdhn-api` package
   is private ([Images](#images)):

   ```sh
   sudo docker login ghcr.io
   ```

3. Set the size of the host in `/etc/tsdhn/worker.env`:

   | Variable                   | Value                                                     |
   | -------------------------- | --------------------------------------------------------- |
   | `TSDHN_WORKER_CONCURRENCY` | Simulations this host runs at once, `1` default           |
   | `TSDHN_NUMBA_THREADS`      | CPUs divided by the concurrency, rounded down             |
   | `TSDHN_WORKER_ID`          | Name in queue records, `tsdhn-worker-HOST-PID` by default |

   A host with 16 CPUs that runs 2 simulations sets `TSDHN_NUMBA_THREADS=8`.
   Each simulation peaks near 0.8 GiB of memory
   ([Reference run](#reference-run)). An empty `TSDHN_NUMBA_THREADS` lets one
   simulation use every CPU, which suits a concurrency of 1.

4. Start the worker and check it:

   ```sh
   alias tsdhn-worker='sudo docker compose --env-file /etc/tsdhn/worker.env -f /etc/tsdhn/compose.worker.yml'
   tsdhn-worker pull
   tsdhn-worker up -d --wait
   tsdhn-worker ps
   ```

   `ps` shows `healthy` once the worker has touched its heartbeat file in the
   last 60 seconds. The worker touches it every 10 seconds while it reaches the
   database. The log says which queue it serves:

   ```sh
   tsdhn-worker logs worker
   ```

   Compose stops with the name of any required value that the env file lacks.

5. On the main host, list the jobs that run and the worker that holds each:

   ```sh
   tsdhn-prod exec postgres psql -U tsdhn -d tsdhn -c "SELECT worker_id, count(*) FROM task_queue.jobs WHERE state = 'leased' GROUP BY worker_id"
   ```

The worker host runs no retention pass. The main host deletes expired outputs
and finished queue rows (`TSDHN_RETENTION_ENABLED=false` on the worker host).

To deploy another release, change `API_IMAGE` in `/etc/tsdhn/prod.env` and in
every worker env, then run `pull` and `up -d` on each host.

#### Checkpoints stay on the host

A running job writes checkpoints to the `jobs-data` volume of the host that runs
it. They are not uploaded. A job that moves to another host starts over from the
first step.

#### Remove a worker host

Stop it:

```sh
tsdhn-worker down
```

Add `-v` to delete the workspaces too. A job the host was running stays leased
until its lease ends, 60 seconds (`TSDHN_WORKER_LEASE_SECONDS`). Then another
worker takes the job and starts it over. Every take-over counts as an attempt,
and a job fails after three. To lose no work, wait until the query above lists
no job for the host before you stop it.

### Backup and restore

The `backup` service runs [`tsdhn-backup`](../deploy/backup/tsdhn-backup) from
the `BACKUP_IMAGE`. At start, and then every `BACKUP_INTERVAL_SECONDS` (a day),
it:

1. dumps the whole `tsdhn` database with `pg_dump`: the web users, sessions and
   simulations, `compute.jobs` and the queue;
2. mirrors the storage bucket, the output files, into its staging volume;
3. writes both to a [restic](https://restic.net) repository in
   `BACKUP_REPOSITORY`, an S3-compatible bucket you own and that is not on this
   host. restic encrypts and authenticates everything with `BACKUP_PASSWORD`
   before it leaves the host;
4. keeps the last 7 daily, 4 weekly and 3 monthly snapshots and prunes the rest;
5. checks the repository's structure and reads one fourteenth of its data, so a
   damaged pack shows up within two weeks.

A failed backup is logged, writes no snapshot and is tried again after 15
minutes. That includes a storage service that does not answer or rejects its
keys: the backup fails instead of recording an empty bucket. It also fails when
the storage service answers but the bucket `TSDHN_S3_BUCKET` is not in it,
because the bucket was deleted or the name is wrong. The worker creates the
bucket when it starts, so a healthy stack always has one. The dump comes before
the mirror, so a file uploaded in between is an extra file in the backup and
never a completed job without its files.

The bucket must exist before the first backup, and its keys need to list, read,
write and delete objects in it. `tsdhn-backup` creates the repository itself on
the first run, and stops with a message when it cannot open the repository, for
instance because the bucket is missing or the password is wrong.

`BACKUP_PASSWORD` lives in `/etc/tsdhn/prod.env` and nowhere in the repository.
Keep a second copy somewhere other than this host, such as a password manager.
Without it the backups cannot be read, and losing the host would lose both.

The backup leaves out the `jobs-data` volume, which holds the work directories
and checkpoints of running jobs, so a restored stack cannot resume a job that
was running. It also leaves out `/etc/tsdhn/prod.env`, the tunnel and the
images. A file that the [output retention](jobs.md#output-retention) deleted
stays in the older snapshots until they rotate out, about three months.

List the snapshots:

```sh
tsdhn-prod --profile restore run --rm --no-deps --entrypoint restic restore snapshots
```

#### Restore

`restore` is a second command of the same image, in the Compose profile
`restore`. It refuses a database that already has the `compute` or `task_queue`
schema, and a bucket that already holds objects, so it cannot overwrite a live
stack. It restores into the database of the stack's own `postgres` service and
the bucket in `TSDHN_S3_*`: the bundled `storage` service, or the external
bucket, which must exist and be empty. To restore into a bucket that holds
leftovers, pass `--wipe-objects` before the snapshot: it deletes every object in
the bucket that the snapshot does not contain.

To rebuild a lost host, install Docker, copy `prod.env` back to
`/etc/tsdhn/prod.env`, log in to the registry and start only the two stores
(leave out `storage` for an external bucket). Starting the whole stack first
would let `backup` write an empty snapshot:

```sh
tsdhn-prod pull
tsdhn-prod up -d postgres storage
tsdhn-prod --profile restore run --rm restore restore
tsdhn-prod up -d
```

The restore takes the latest snapshot. Name another with
`restore restore SNAPSHOT_ID`. The last command starts the rest of the stack.
`compute-migrate` creates the queue roles and their grants again, and
`web-grants` does the same for the web role, because the dump carries neither
owners nor policies. Each restored job then reads as it did: status, parameters,
arrival times and the output files. A snapshot taken before the output retention
deleted a job's files restores those files, and the worker's next hourly pass
deletes them again.

### Recovery test

A backup counts once it has been restored. Run this on any host that has Docker,
`jq`, the images and `prod.env`:

```sh
sudo scripts/restore-drill.sh --env-file /etc/tsdhn/prod.env
```

The script starts a second copy of the stack under its own Compose project name,
with its own empty volumes and the bundled storage, even when production uses an
external bucket. It restores the latest backup into the copy, starts the API on
it, and reads the latest completed job through `GET /api/v1/jobs/ID`, the job's
output list and the first output's download. It prints the job and the size of
the file, then removes the copy. The running stack is untouched, and the copy
only reads the backup bucket. A successful run ends like this:

```text
2026-10-16T14:48:58Z restored 1 compute jobs and 9 objects
== job b6e1f5a0-2c1b-4a7c-9c7a-3f7b6a5d9e11
{ "status": "completed", "step": "copy_ttt_pdf", ... }
== output input: 96 bytes
== restore drill passed
```

`--snapshot ID` tests an older snapshot, and `--keep` leaves the copy running
and prints the command that removes it. The run takes under a minute with the
images present.

[Testing](testing.md#backup-and-restore-test) describes the test that drives the
same commands against throwaway containers.

To check that a worker killed in the middle of a job resumes it, run
[`scripts/e2e/crash_recovery_e2e.sh`](../scripts/e2e/crash_recovery_e2e.sh)
against a running Compose stack, or start the manual workflow
`crash-recovery.yml`, which builds the images and runs it. The script:

1. submits a simulation and waits until the tsunami step has written
   checkpoints;
2. kills the worker with `SIGKILL` and starts it again;
3. waits for the queue to reclaim the expired lease, which raises the job's
   attempt, and for the job to complete rather than fail;
4. looks for `resuming tsunami run from step N` in the worker log, which proves
   that the second attempt continued from a checkpoint;
5. checks the stored outputs.

It also covers the sweep of old work directories and a storage outage during the
upload, which retries instead of failing the job.

### Reference run

One simulation through web on an 8-CPU, 30 GB host, with `ORIGIN` and the
loopback port set for a local check and a placeholder `TUNNEL_TOKEN`: Mw 8.0,
depth 25 km, latitude -12, longitude -77.5, 2026-10-16 12:00 UTC. Sign-up,
submission, the progress stream and every download went through the web port.

| Measure                                 | Value                                             |
| --------------------------------------- | ------------------------------------------------- |
| `up -d` with images present, to healthy | 58 s                                              |
| Queued to finished                      | 12 min 40 s (the worker started 2 s after submit) |
| Steps in the progress stream            | 8 (`total_steps`)                                 |
| Peak memory, worker                     | 554 MiB (`docker stats`), 809 MiB cgroup peak     |
| Peak memory, API, storage, PostgreSQL   | 141, 189 and 91 MiB                               |
| Peak memory, web                        | 42 MiB                                            |
| Outputs                                 | 8 files, 1,862,755 bytes                          |

| Output              | Type | Bytes     |
| ------------------- | ---- | --------- |
| `max_height_map`    | PDF  | 1,061,493 |
| `arrival_time_map`  | PDF  | 717,296   |
| `mareogram`         | SVG  | 80,469    |
| `calculation`       | JSON | 1,019     |
| `travel_times_json` | JSON | 1,285     |
| `travel_times_csv`  | CSV  | 689       |
| `runtime`           | JSON | 408       |
| `input`             | JSON | 96        |

A job queued with the worker stopped held its stream open through web for 1800
seconds. The API then closed it cleanly: 90 keepalive comments, 20 seconds
apart, and no gap longer than that.

### Licence

The TTT SDK licence, `doc/TTTSDK_license.txt` in the SDK, reads:

> Users of the TTT SDK may build their own application by linking to the TTT
> SDK. They may also use the ttt_client executable; output from this tool may be
> used with GMT to make various maps. The TTT SDK and associated files may not
> be distributed; interested parties should contact ITIC/NOAA for further
> details.

It does not mention a hosted service. Running `ttt_client` on your own host is
permitted. Publishing an image that contains the SDK is distribution.
