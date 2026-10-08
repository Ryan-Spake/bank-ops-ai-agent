"""`dbt parse` compiles every model, source, seed and test without touching data,
so broken refs or YAML fail here (and in CI) before anyone runs a build."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

DBT_DIR = Path(__file__).resolve().parents[1] / "dbt"
DBT = shutil.which("dbt", path=str(Path(sys.executable).parent))


@pytest.mark.skipif(DBT is None, reason="dbt not installed in this environment")
def test_dbt_project_parses():
    result = subprocess.run(
        [DBT, "parse", "--profiles-dir", ".", "--no-partial-parse"],
        cwd=DBT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout[-2000:]
