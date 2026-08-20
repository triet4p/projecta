import pytest
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
