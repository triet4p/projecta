import pytest
from preflight_sprint12_f12_offline_contracts_v5 import (
    REQUIRED_BOUND_PATHS,
    _verify_bound_digests,
    run_preflight,
)


def test_v5_preflight_runs_reuse_and_source_proof_fixtures():
    result = run_preflight()
    assert result["status"] == "OFFLINE_CONTRACTS_READY_ZERO_CALL_V5"
    assert result["providerCalls"] == 0


def test_v5_preflight_rejects_removed_or_extra_binding():
    with pytest.raises(ValueError, match="exact"):
        _verify_bound_digests({"boundDigests": {}})
    bindings = {path: "sha256:unused" for path in REQUIRED_BOUND_PATHS}
    bindings["scripts/unexpected.py"] = "sha256:unexpected"
    with pytest.raises(ValueError, match="exact"):
        _verify_bound_digests({"boundDigests": bindings})
