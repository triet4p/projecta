"""Live evaluation fails closed when required configuration is absent."""

import json
import os
import subprocess
import sys
from pathlib import Path


def test_live_runner_fails_without_required_configuration() -> None:
    env = os.environ.copy()
    for name in ("PROJECTA_LLM_TYPE", "PROJECTA_LLM_BASE_URL", "PROJECTA_LLM_API_KEY"):
        env.pop(name, None)
    env.pop("PROJECTA_LLM_MODEL", None)
    result = subprocess.run(
        [sys.executable, "evaluation/sprint-5/run_live.py"],
        cwd=Path(__file__).parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["error"] == "missing_required_llm_configuration"
