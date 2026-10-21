# Contributing

## Set up

Follow [Install](../readme.md#install) in the README. `mise run install`
installs the Python and web dependencies from the lockfiles.

## Check a change

`mise run check` runs lint, typecheck, the unit tests and the builds. It needs
no services and no GMT. To run one part, use `mise run lint`,
`mise run typecheck`, `mise run test` or `mise run build`. `lint` has `:py` and
`:web` subtasks. The other three have a `:py` subtask for the Python part; run
the web part alone with `bun --filter '*' typecheck`, `bun --filter '*' test` or
`bun --filter web build`.

[Testing](../docs/testing.md) lists every suite: database-backed tests, the
golden pipeline test and the comparisons with the MATLAB and Fortran programs.
[Parity](../docs/parity.md) explains the comparisons.

## Change a component

Read [Architecture](../docs/architecture.md) before you change a boundary
between components, and the manual page for the behavior you change.
[Where the code is](../docs/architecture.md#where-the-code-is) maps behavior to
files. Each package readme has its commands.

After you change an API route or schema, regenerate the client as described in
[`libs/api-client`](../libs/api-client/readme.md#regenerate).

Numerical changes need a focused behavior test. Run the golden or parity tests
when the change affects their output. If expected data changes, say why in the
commit and cite the source or research case.

## Format

`mise run fix` formats Python, JavaScript, TypeScript, Markdown, YAML and JSON
and applies safe lint fixes. `mise run lint` checks without writing.
