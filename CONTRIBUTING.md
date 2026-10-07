# Contributing

Install the pinned toolchain and dependencies before changing the repository:

```sh
mise install
mise run install
mise run web-install
```

Run the checks that match the change. The fast suites do not need services:

```sh
mise run test
mise run web-test
mise run lint-all
```

Database-backed tests use the project-local PostgreSQL cluster and disposable
databases:

```sh
mise run test-integration
```

The full scientific pipeline needs GMT and `ttt_client`:

```sh
mise run test-golden
```

Compare the active Python stages with saved MATLAB and Fortran results with:

```sh
mise run test-parity
```

The Fortran comparison cases need the compiled programs in `TSDHN_TOOLS_DIR`.
The MATLAB capture command needs its container and license; ordinary parity
tests read the saved fixtures.

## Change a component

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) before changing a boundary. Read the
manual page for the behavior being changed. The package READMEs describe the
local code map and package-specific commands.

After changing an API route or schema, run:

```sh
mise run gen-client
```

Numerical changes need focused behavior tests. Run golden or parity tests when
the changed behavior affects their outputs, and explain changed expected data
with the relevant source or research case.

Format JavaScript and TypeScript with the repository task and Markdown with the
repository's Markdown formatter. Keep prose and code comments short and use one
term for each concept.
