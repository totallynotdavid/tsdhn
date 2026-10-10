# TSDHN web

`apps/web` is the SvelteKit web app. It provides authentication, simulation
history, the input form, progress pages, and output downloads.

The browser talks to SvelteKit. Server code calls the FastAPI compute service
with `COMPUTE_API_URL` and `COMPUTE_API_TOKEN`. See
[Architecture](../../docs/architecture.md) for data ownership and
[Deploy](../../docs/deploy.md) for the local stack.

## Development

From the repository root:

```sh
bun install
bun --filter web dev
bun --filter web check
bun --filter web build
bun --filter web test
```

The Vitest suite is service-free. Database-backed tests use:

```sh
mise run test-integration
```

## Preview

`mise run web:preview` serves the app without Postgres, the compute service or a
login step:

```sh
mise run web:preview
mise run web:preview --host 100.64.0.1 --port 8080
```

The host defaults to `0.0.0.0` and the port to `5174`, so another machine on the
network, such as a Tailscale peer, reaches the app at `http://<host>:5174`.

The preview signs in the demo user on the first request to any page except
`/login` and `/signup`. Those two pages show the signed-out forms, and
`demo@tsdhn.test` with password `demo-preview` signs in through them.

It holds six simulations: two completed, one running, one queued, one failed,
and one that was never sent to the compute service. A simulation you submit
queues, advances through the eight engine steps every 2.5 seconds, and
completes. One whose source is deeper than 300 km fails at the third step.
Downloads return small canned files. The data resets on every start.

The map tiles load from the internet, so the map needs a network connection.

The preview refuses to start when `NODE_ENV` is `production` or `DATABASE_URL`
is set. [Architecture](../../docs/architecture.md#preview-mode) describes how it
replaces the database and the compute service.

## Database

Web tables are declared in `src/lib/server/db/schema.ts`. Better Auth tables are
generated with:

```sh
bun --filter web auth:schema
```

Generate and apply web migrations with a database administrator connection:

```sh
bun --filter web db:generate
bun --filter web db:migrate
```

`src/lib/server/db/compute.ts` describes the columns read from `compute.jobs`.
It is not part of the web migration schema.

## Server modules

[Architecture](../../docs/architecture.md#where-the-code-is) lists the modules
under `src/lib/server/`. Route handlers check the session and ownership before
they call the compute API.
