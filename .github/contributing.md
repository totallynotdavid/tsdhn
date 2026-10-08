# Contributing

## Set up

Follow [Install](../readme.md#install) in the README, then install the web app
dependencies:

```sh
mise run web-install
```

## Check a change

Run the checks that match the change. The first three need no services and no
GMT:

```sh
mise run test
mise run web-test
mise run lint-all
```

[Testing](../docs/testing.md) lists every suite: database-backed tests, the
golden pipeline test and the comparisons with the MATLAB and Fortran programs.
[Parity](../docs/parity.md) explains the comparisons.

## Change a component

Read [Architecture](../docs/architecture.md) before you change a boundary
between components, and the manual page for the behavior you change. Each
package readme has its code map and commands.

After you change an API route or schema, regenerate the client as described in
[`libs/api-client`](../libs/api-client/readme.md#regenerate).

Numerical changes need a focused behavior test. Run the golden or parity tests
when the change affects their output. If expected data changes, say why in the
commit and cite the source or research case.

## Format

Format JavaScript and TypeScript with `mise run fmt-js`. Format Markdown with:

```sh
bunx prettier --print-width 80 --prose-wrap always --write '**/*.md'
```
