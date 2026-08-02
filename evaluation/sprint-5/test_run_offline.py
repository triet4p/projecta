"""Runner tests use the committed fixture contract and no network."""

import json
import subprocess
import sys
from pathlib import Path


def test_offline_runner_passes_complete_replay_fixture() -> None:
    result = subprocess.run(
        [sys.executable, "evaluation/sprint-5/run_offline.py"],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "passed"
