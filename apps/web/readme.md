# TSDHN web

`apps/web` is the SvelteKit application for authenticated simulation requests,
calculation previews, progress display, and report downloads.

The app uses a server-side web backend pattern:

- Browser requests go to SvelteKit routes.
- SvelteKit server code calls FastAPI with `BACKEND_SERVICE_TOKEN`.
- The service token stays in server-side code.
- SQLite/libSQL stores data managed by the web app, such as users and submitted simulation
  records.
- The FastAPI compute plane manages live simulation progress, worker state, and
  MinIO artifact pointers.

## Commands

From the repository root:

```sh
bun install
bun --filter web dev
bun --filter web check
bun --filter web build
```

The root package also exposes:

```sh
mise run web-dev
mise run web-check
mise run web-build
```

## Environment

Create `apps/web/.env` from [`apps/web/.env.example`](./.env.example).

| Variable                | Example from `.env.example` | Purpose                                         |
| ----------------------- | --------------------------- | ----------------------------------------------- |
| `DATABASE_URL`          | `file:local.db`             | Drizzle/libSQL connection string                |
| `ORIGIN`                | `http://localhost:5173`     | Public origin used by SvelteKit and Better Auth |
| `BETTER_AUTH_SECRET`    | empty                       | Better Auth session secret                      |
| `BACKEND_URL`           | `http://localhost:8000`     | FastAPI backend base URL                        |
| `BACKEND_SERVICE_TOKEN` | empty                       | Bearer token sent only by SvelteKit server code |

`BETTER_AUTH_SECRET` and `BACKEND_SERVICE_TOKEN` must be non-empty outside
local-only development.

## Database

The app uses Drizzle with SQLite/libSQL. The schema lives in
[`src/lib/server/db/schema.ts`](./src/lib/server/db/schema.ts), and Better Auth
tables are generated into [`src/lib/server/db/auth.schema.ts`](./src/lib/server/db/auth.schema.ts).

```sh
bun --filter web db:generate
bun --filter web db:migrate
bun --filter web db:push
bun --filter web db:studio
```

Regenerate the Better Auth schema with:

```sh
bun --filter web auth:schema
```

## Backend integration

Typed backend calls use `@tsdhn/api-client` from
[`libs/api-client`](../../libs/api-client/readme.md). The wrapper in
[`src/lib/server/api.ts`](./src/lib/server/api.ts) attaches the bearer token and
uses SvelteKit's request-aware `fetch` for server-side calls.

Current server-side backend calls include:

- `POST /api/v1/calculations` from [`src/routes/api/calculations/+server.ts`](./src/routes/api/calculations/+server.ts)
- `POST /api/v1/jobs` from [`src/lib/server/dispatch.ts`](./src/lib/server/dispatch.ts)
- `GET /api/v1/jobs/{id}` from app-owned simulation pages and dashboard status sync
- `GET /api/v1/jobs/{id}/events` proxied by [`src/routes/(app)/simulations/[id]/events/+server.ts`](./src/routes/%28app%29/simulations/%5Bid%5D/events/+server.ts)
- `GET /api/v1/jobs/{id}/report` proxied by [`src/routes/(app)/simulations/[id]/report/+server.ts`](./src/routes/%28app%29/simulations/%5Bid%5D/report/+server.ts)

## Docker

The root Compose file can run the web app with the backend stack:

```sh
docker compose --profile web up
```

The web image is built from [`deploy/web.Dockerfile`](../../deploy/web.Dockerfile).
