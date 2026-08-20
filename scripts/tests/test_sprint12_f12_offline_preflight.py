"""Zero-call preflight tests for S12-f-12 offline preparation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from preflight_sprint12_f12_offline_contracts import run_preflight

REVIEW = (
    ROOT
    / "evaluation/sprint-12/optimization/"
    "s12-f-12-offline-contracts-review.v1.json"
)


def test_f12_preflight_is_offline_and_unissued() -> None:
    result = run_preflight()
    assert result["status"] == "OFFLINE_CONTRACTS_READY_ZERO_CALL"
    assert result["providerCalls"] == 0
    assert result["providerExecutionAuthorized"] is False
    assert result["preregistrationIssued"] is False
    assert result["heldOutAccess"] is False
    assert result["oracleFixtureCount"] == 3


def test_rm21_review_withholds_preregistration_for_measurement_blockers() -> None:
    import json

    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert review["status"] == (
        "OWNER_REVIEW_WITHHELD_MEASUREMENT_CONTRACT_BLOCKERS"
    )
    assert len(review["blockingFindings"]) == 6
    assert review["decision"]["rm21Approved"] is False
    assert review["decision"]["preregistrationPreparationAuthorized"] is False
    assert review["decision"]["providerExecutionAuthorized"] is False
    assert review["decision"]["heldOutAccessAuthorized"] is False
    assert review["decision"]["stageBAuthorized"] is False
