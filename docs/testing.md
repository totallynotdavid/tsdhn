# Test the engine

Each test group answers a different question. None of them establishes that the
scientific model is correct by itself.

## Common commands

| Command                     | Purpose                                   |
| --------------------------- | ----------------------------------------- |
| `mise run test`             | Run the fast Python test suite            |
| `mise run test-integration` | Run database-backed tests                 |
| `mise run web-test`         | Run the fast web test suite               |
| `mise run lint-all`         | Run Python and JavaScript checks          |
| `mise run gen-client`       | Regenerate the OpenAPI client             |
| `mise run test-golden`      | Run the full pipeline regression          |
| `mise run test-parity`      | Compare Python output with older programs |

## Fast behavior tests

`mise run test` runs the Python suite without services. The suite covers source
parameters, longitude conversion, file formats, numerical update rules,
checkpoints, resume behavior, and report transformations with focused inputs.

Run one test with:

```sh
uv run pytest packages/tsdhn/tests/test_tsunami.py::test_mass_step_hand_computed
```

## Golden pipeline tests

`mise run test-golden` runs the full Python pipeline with GMT and `ttt_client`.
It checks output sets, fixed-width fingerprints, and selected spatial values for
a saved scenario. A golden result answers whether the output changed for that
scenario. It does not establish which result is physically correct.

## Legacy comparisons

`mise run test-parity` compares Python checkpoints with saved MATLAB data and
compiled Fortran output. It checks whether Python matches the selected reference
within an explicit tolerance. See [`legacy.md`](legacy.md) for the active
reference map.

The saved MATLAB fixtures are captured evidence. A refresh records the input
case, source, checkpoint names, and reason for the new capture. The capture
command is:

```sh
uv run python scripts/capture_matlab_fixtures.py fault_plane
```

It needs the MathWorks container and license. Ordinary tests read the saved
fixtures and do not start MATLAB. Fortran cases need compiled tools in
`TSDHN_TOOLS_DIR`.

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

Start investigating a comparison failure at the earliest failing checkpoint.
Later checkpoints can differ because an earlier stage changed. Keep units,
coordinate frames, dtypes, indexing, and output precision explicit in expected
values.
