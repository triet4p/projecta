from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from preflight_sprint12_f12_rm22_preparation import run_preflight
from run_sprint12_f12_stage_a import F12StageAError, run_stage_a, validate_preparation


def test_historical_rm22_preflight_rejects_after_rm25_authorization() -> None:
    with pytest.raises(ValueError, match="f12 authorization already exists"):
        run_preflight()


def test_unauthorized_runner_path_never_calls_adapter() -> None:
    class Spy:
        calls = 0

        def capture_stage(self, **_: object) -> object:
            self.calls += 1
            raise AssertionError("capture must not happen")

    spy = Spy()
    with pytest.raises(F12StageAError, match="authorization"):
        run_stage_a(provider_adapter=spy, authorization_path=None)
    assert spy.calls == 0


def test_preparation_lineage_and_no_overwrite_guard_are_bound() -> None:
    package = validate_preparation()
    assert package["outputPath"] == "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v1.json"
    assert package["retryPolicy"] == "none"
    assert package["outputOverwrite"] is False
