from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PREPARATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm24-preparation.v1.json"
sys.path.insert(0, str(ROOT / "scripts"))

import preflight_sprint12_f12_rm24 as rm24


def test_rm24_preparation_remains_zero_call_historical_evidence() -> None:
    preparation = json.loads(PREPARATION.read_text(encoding="utf-8"))
    assert preparation["status"] == "PREPARED_PENDING_RM25_OWNER_AUTHORIZATION"
    assert preparation["providerCallsPerformedAtPreparation"] == 0
    assert preparation["providerExecutionAuthorized"] is False
    assert preparation["offlineEvidence"]["reportPathMustBeAbsent"] is True


def test_rm24_binds_owner_review_and_exact_execution_commit() -> None:
    preparation = json.loads(PREPARATION.read_text(encoding="utf-8"))
    assert preparation["ownerReview"]["digest"].startswith("sha256:")
    assert preparation["issuedLineage"]["executionCommit"] == "e047911e2e2d513f2b8751965dd702b2c1fe9d5a"
    assert preparation["nextGate"] == "S12-RM-25_OWNER_REVIEW_AND_OPTIONAL_ONE_RUN_AUTHORIZATION"


def test_rm24_preflight_cannot_be_reused_after_rm25_transition() -> None:
    with pytest.raises(ValueError, match="current-state digest mismatch"):
        rm24.run_preflight()


def test_rm25_review_digest_binds_immutable_rm24_preparation() -> None:
    review = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-f-12-rm25-owner-review.v1.json"
        ).read_text(encoding="utf-8")
    )
    expected = "sha256:" + hashlib.sha256(PREPARATION.read_bytes()).hexdigest()
    assert review["reviewedPreparation"]["digest"] == expected
