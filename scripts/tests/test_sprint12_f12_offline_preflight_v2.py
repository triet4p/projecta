import json
from pathlib import Path

import pytest
import preflight_sprint12_f12_offline_contracts_v2 as offline_preflight
from preflight_sprint12_f12_offline_contracts_v2 import (
    _verify_bound_digests,
    run_preflight,
)


def test_v2_preflight_runs_bound_zero_call_fixtures():
    result = run_preflight()
    assert result["status"] == "OFFLINE_CONTRACTS_READY_ZERO_CALL_V2"
    assert result["providerCalls"] == 0
    assert result["oracleArms"] == 3


def test_v2_preflight_rejects_tampered_bound_digest():
    with pytest.raises(ValueError, match="digest mismatch"):
        _verify_bound_digests(
            {
                "boundDigests": {
                    "scripts/sprint12_f12_two_step_contracts_v2.py": "sha256:tampered"
                }
            }
        )


def test_v2_preflight_rejects_missing_bound_artifact():
    with pytest.raises(ValueError, match="missing"):
        _verify_bound_digests(
            {"boundDigests": {"scripts/does-not-exist.py": "sha256:missing"}}
        )


def test_v2_allows_rm24_preparation_but_rejects_true_authorization():
    preparation = Path(
        offline_preflight.ROOT
        / "evaluation/sprint-12/optimization/s12-f-12-rm24-preparation.v1.json"
    )
    assert preparation.exists()
    assert preparation not in list(
        offline_preflight.ROOT.glob(
            "evaluation/sprint-12/optimization/s12-f-12-*-authorization*.json"
        )
    )
    result = run_preflight()
    assert result["providerCalls"] == 0

    authorization = (
        offline_preflight.ROOT
        / "evaluation/sprint-12/optimization/s12-f-12-rm25-test-authorization.v1.json"
    )
    authorization.write_text(
        json.dumps(
            {
                "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
                "experimentId": "s12-f-12",
                "providerExecutionAuthorized": True,
            }
        ),
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="f12 authorization artifact exists"):
            run_preflight()
    finally:
        authorization.unlink(missing_ok=True)
