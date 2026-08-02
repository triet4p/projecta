"""Import-order regressions for provider and extraction package boundaries."""

import subprocess
import sys


def test_replay_gateway_imports_before_application_composition() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from projecta_api.llm.replay import ReplayGateway; "
            "from projecta_api.main import create_app",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
