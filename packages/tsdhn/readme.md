# tsdhn

`tsdhn` contains the research CLI and shared simulation engine. The FastAPI
deployment imports this package as an adapter; API and CLI behavior must flow
through the same engine contracts.

The public interface is the `tsdhn` command. Model datasets are versioned
release assets and are resolved by the runtime layer, not by deployment-specific
code.
