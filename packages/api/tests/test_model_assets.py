import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("module", ["api.main", "api.worker"])
def test_process_refuses_to_start_without_model_assets(
    module: str, tmp_path: Path
) -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", module],
        env={"TSDHN_MODEL_DIR": str(tmp_path), "PATH": ""},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert result.stderr.startswith("error: Invalid TSDHN model directory")
    assert str(tmp_path) in result.stderr
    assert "Traceback" not in result.stderr
