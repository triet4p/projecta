from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PREPARATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm24-preparation.v1.json"
sys.path.insert(0, str(ROOT / "scripts"))

import preflight_sprint12_f12_rm24 as rm24


def test_rm24_preflight_is_zero_call_and_pending_rm25() -> None:
    result = rm24.run_preflight(require_clean_tree=False)
    assert result["status"] == "S12_RM24_READY_ZERO_CALL_PENDING_RM25"
    assert result["providerCalls"] == 0
    assert result["providerExecutionAuthorized"] is False
    assert result["outputPathAbsent"] is True


def test_rm24_binds_owner_review_and_exact_execution_commit() -> None:
    preparation = json.loads(PREPARATION.read_text(encoding="utf-8"))
    assert preparation["ownerReview"]["digest"].startswith("sha256:")
    assert preparation["issuedLineage"]["executionCommit"] == "e047911e2e2d513f2b8751965dd702b2c1fe9d5a"
    assert preparation["nextGate"] == "S12-RM-25_OWNER_REVIEW_AND_OPTIONAL_ONE_RUN_AUTHORIZATION"


def test_rm24_rejects_tampered_owner_review_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    original = rm24._load

    def tampered(path: Path) -> dict[str, object]:
        value = original(path)
        if path == PREPARATION:
            value = copy.deepcopy(value)
            value["ownerReview"]["digest"] = "sha256:" + ("0" * 64)
        return value

    monkeypatch.setattr(rm24, "_load", tampered)
    with pytest.raises(ValueError, match="digest mismatch"):
        rm24.run_preflight()
