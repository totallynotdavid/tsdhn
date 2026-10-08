# Testing

Each suite answers a different question.

| Command                     | Question                                       | Needs                               |
| --------------------------- | ---------------------------------------------- | ----------------------------------- |
| `mise run test`             | Do the Python units behave as specified?       | nothing                             |
| `mise run web-test`         | Do the web units behave as specified?          | nothing                             |
| `mise run test-integration` | Do the queue, roles and migrations work?       | PostgreSQL, which the task starts   |
| `mise run test-golden`      | Did the full pipeline output change?           | GMT and `ttt_client`                |
| `mise run test-parity`      | Does Python match the MATLAB and Fortran runs? | `TSDHN_TOOLS_DIR` for Fortran cases |
| `mise run lint-all`         | Do Python and JavaScript pass the linters?     | nothing                             |

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
