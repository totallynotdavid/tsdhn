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

- `src/lib/server/compute-api.ts`: server-only typed compute API client.
- `src/lib/server/submit-simulation.ts`: submission and retry handling.
- `src/lib/server/simulation-repository.ts`: simulation queries.
- `src/lib/server/simulation-details.ts`: simulation and compute-state join.
- `src/lib/server/outputs.ts`: output-name validation.
- Route handlers: session and ownership checks before compute API calls.
