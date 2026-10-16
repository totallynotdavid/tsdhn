# Testing

Each suite answers a different question.

| Command                     | Question                                                                         | Needs                                                                     |
| --------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `mise run test`             | Do the Python units behave as specified?                                         | nothing                                                                   |
| `mise run web-test`         | Do the web units behave as specified?                                            | nothing                                                                   |
| `mise run test-integration` | Do the queue, roles, migrations and backups work?                                | PostgreSQL, which the task starts; Docker for the backup and expiry tests |
| `mise run test-golden`      | Did the full pipeline output change?                                             | GMT and `ttt_client`                                                      |
| `mise run test-parity`      | Does Python match the MATLAB and Fortran runs?                                   | `TSDHN_TOOLS_DIR` for Fortran cases                                       |
| `mise run lint-all`         | Do the linters pass, and do the Dockerfile tool versions match `.tool-versions`? | nothing                                                                   |

Run one test with:

```sh
uv run pytest packages/tsdhn/tests/test_tsunami.py::test_mass_step_hand_computed
```

## Fast tests

`mise run test` runs the Python suite without services or GMT. When the GMT
library cannot load, pytest names the GMT-backed module it does not collect in
its report header. The suite covers source parameters, longitude conversion,
file formats, numerical update rules, checkpoints, resume behavior and report
transformations with focused inputs.

## Backup and restore test

`mise run test-integration` includes
`packages/api/tests/test_backup_restore.py`. It builds the backup image and
starts throwaway PostgreSQL and RustFS containers: a source holding a finished
job, an off-host bucket and an empty target. It runs `tsdhn-backup backup` and
`tsdhn-backup restore` in the image, then reads the restored job through the
API's routes. It also checks that the bucket holds no plaintext, that a wrong
password fails, that a backup fails and writes no snapshot when it cannot list
the storage service or the bucket is gone, and that a restore refuses a database
that already has the compute schema or a bucket that already holds objects. It
skips when Docker is missing or an image cannot be pulled.
[Deploy](deploy.md#recovery-test) runs the same restore against the production
stack's own images.

## Output expiry test

`packages/api/tests/test_output_expiry_integration.py` runs the worker's
retention pass against PostgreSQL and a throwaway RustFS container. It stores
files, including keys two levels deep, for an old and a recent job, and checks
that the pass leaves the old job's prefix empty, keeps the recent job's files
and marks only the old job expired. A storage service that does not answer
leaves the job's files listed for the next pass. The same file checks that the
worker creates a missing bucket at start and survives a storage service that
does not answer. It skips when Docker is missing.

## Golden tests

`mise run test-golden` runs the full Python pipeline. It checks output sets,
fixed-width fingerprints and selected spatial values for a saved scenario. A
golden result tells you whether the output changed for that scenario.

## Parity tests

`mise run test-parity` compares Python checkpoints with saved MATLAB data and
compiled Fortran output within an explicit tolerance. [Parity](parity.md)
describes the references, the Fortran tools and the MATLAB capture.

## Choose evidence for a change

| Change                                     | Evidence                                          |
| ------------------------------------------ | ------------------------------------------------- |
| Refactor with unchanged numerical behavior | Focused tests and relevant comparison             |
| File-format change                         | Reader/writer test and downstream stage test      |
| Dtype or evaluation-order change           | Edge cases, comparison, and spatial golden output |
| New scientific relation                    | Independent worked example and source citation    |
| Boundary or wet-cell rule                  | Hand-computed small-grid test and comparison      |
| Checkpoint layout or meaning               | Resume equivalence and version rejection          |
| Display transformation                     | Raw-value preservation and report regression      |

When a comparison fails, start at the earliest failing checkpoint, because later
checkpoints differ when an earlier stage changed. Keep units, coordinate frames,
dtypes, indexing and output precision explicit in expected values.
