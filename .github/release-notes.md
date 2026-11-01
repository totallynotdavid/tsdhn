tsdhn 0.3.0 is out.

This release adds the `tsdhn-ttt` Python package. It computes tsunami
travel-time grids from GMT bathymetry files without a separately compiled
client. Install the `tsdhn-ttt` wheel attached to this GitHub release and run
`tsdhn-ttt --help` for the command options.

Its default mode now uses float64 calculations, starts the wavefront around the
epicenter, and measures segments along great-circle paths between their actual
grid-node latitudes. This reduces the arrival-time differences caused by float32
rounding, start-node selection, and the previous latitude approximation. The
returned `TravelTimes.hours` values are float64; GMT output files remain
float32.

Use `--client-compatible` when a result must match the legacy `ttt_client`
behavior. The package documents both modes and checks the default against
closed-form travel times.

## Known problems

None known.

## Upgrade

Python package: `uv pip install tsdhn==0.3.0` (Python 3.14 or newer), then
`tsdhn assets install` to fetch the matching model bundle.

Containers: pull `ghcr.io/totallynotdavid/tsdhn-api:v0.3.0`, `tsdhn-web:v0.3.0`,
`tsdhn-backup:v0.3.0` and `tsdhn-toolchain:v0.3.0`, then follow
`docs/deploy.md`.

Report problems at <https://github.com/totallynotdavid/tsdhn/issues>.
