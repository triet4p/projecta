import pytest
from preflight_sprint12_f12_offline_contracts_v5 import (
    REQUIRED_BOUND_PATHS,
    _verify_bound_digests,
    run_preflight,
)


def test_historical_v5_preflight_rejects_after_rm25_authorization():
    with pytest.raises(ValueError, match="f12 authorization or preregistration artifact exists"):
        run_preflight()


def test_v5_preflight_rejects_removed_or_extra_binding():
    with pytest.raises(ValueError, match="exact"):
        _verify_bound_digests({"boundDigests": {}})
    bindings = {path: "sha256:unused" for path in REQUIRED_BOUND_PATHS}
    bindings["scripts/unexpected.py"] = "sha256:unexpected"
    with pytest.raises(ValueError, match="exact"):
        _verify_bound_digests({"boundDigests": bindings})
