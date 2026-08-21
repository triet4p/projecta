"""Zero-call preflight tests for S12-f-12 offline preparation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from preflight_sprint12_f12_offline_contracts import run_preflight

REVIEW = (
    ROOT
    / "evaluation/sprint-12/optimization/"
    "s12-f-12-offline-contracts-review.v1.json"
)


def test_historical_f12_preflight_rejects_after_rm25_authorization() -> None:
    with pytest.raises(ValueError, match="f12 authorization artifact exists"):
        run_preflight()


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
