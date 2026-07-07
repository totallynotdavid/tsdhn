# tsdhn

`tsdhn` contains the CLI for researchers and the shared simulation engine. The
API, worker, and CLI should use this same engine.

The public interface is the `tsdhn` command. Model datasets are versioned
release assets and are resolved by the runtime code, not by deployment-specific
code.
