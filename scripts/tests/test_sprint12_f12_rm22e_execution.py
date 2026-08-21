from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v6 as v6
from sprint12_provider_adapter import ProviderCapture


class MockStageAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def capture_stage(self, **kwargs: object) -> ProviderCapture:
        self.calls.append(kwargs)
        if kwargs["stage"] == "stage1":
            payload = {
                "schemaVersion": "s12-f-12.stage1.entity-envelope.v2",
                "entities": [],
                "abstention": {"required": True, "reason": "mock"},
            }
        else:
            payload = {
                "schemaVersion": "s12-f-12.stage2.relation-envelope.v2",
                "relations": [],
                "abstention": {"required": True, "reason": "mock"},
            }
        return ProviderCapture(
            payload=payload,
            usage={
                "inputTokens": 1000,
                "promptCacheHitTokens": 0,
                "promptCacheMissTokens": 1000,
                "outputTokens": 100,
            },
            retry_count=0,
        )


def _authorization(path: Path) -> Path:
    package = json.loads(v6.PACKAGE.read_text(encoding="utf-8"))
    freeze = json.loads(v6.FREEZE.read_text(encoding="utf-8"))
    target = ROOT / "evaluation/sprint-12/optimization/.s12-f-12-rm22e-test-authorization.json"
    payload = {
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "experimentId": "s12-f-12",
        "providerExecutionAuthorized": True,
        "providerCalls": 144,
        "retryPolicy": "none",
        "commitSha": package["commitSha"],
        "executionPackage": {"digest": v6.digest(v6.PACKAGE)},
        "freezeRecord": {"digest": v6.digest(v6.FREEZE)},
        "outputPath": path.relative_to(ROOT).as_posix(),
        "costCeilingUsd": "10.00",
        "heldOutInspected": False,
        "heldOutAccessAuthorized": False,
        "validationAccessAuthorized": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
    }
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert freeze["commitSha"] == package["commitSha"]
    return target


def test_v7_unauthorized_path_has_zero_calls() -> None:
    adapter = MockStageAdapter()
    with pytest.raises(RuntimeError, match="authorization"):
        v6.run_stage_a(
            provider_adapter=adapter,
            authorization_path=None,
            output_path=v6.OUTPUT,
        )
    assert len(adapter.calls) == 0


def test_v7_authorized_e2e_is_144_calls_and_96_branches() -> None:
    v6.OUTPUT.unlink(missing_ok=True)
    authorization = _authorization(v6.OUTPUT)
    adapter = MockStageAdapter()
    try:
        report = v6.run_stage_a(
            provider_adapter=adapter,
            authorization_path=authorization,
            output_path=v6.OUTPUT,
        )
        assert len(adapter.calls) == 144
        assert report["accounting"]["providerCallsAttempted"] == 144
        assert len(report["caseRecords"]) == 48
        assert sum(
            1
            for record in report["caseRecords"]
            for arm in ("predicted-entities", "gold-entities")
            if arm in record["arms"]
        ) == 96
        assert report["artifactVersion"] == "s12-f-12.stage-a-report.v6"
        assert v6.OUTPUT.is_file()
    finally:
        authorization.unlink(missing_ok=True)
        v6.OUTPUT.unlink(missing_ok=True)


def test_v7_second_execution_is_rejected_without_calls() -> None:
    v6.OUTPUT.unlink(missing_ok=True)
    authorization = _authorization(v6.OUTPUT)
    first_adapter = MockStageAdapter()
    second_adapter = MockStageAdapter()
    try:
        v6.run_stage_a(
            provider_adapter=first_adapter,
            authorization_path=authorization,
            output_path=v6.OUTPUT,
        )
        with pytest.raises(RuntimeError, match="overwrite|output"):
            v6.run_stage_a(
                provider_adapter=second_adapter,
                authorization_path=authorization,
                output_path=v6.OUTPUT,
            )
        assert len(first_adapter.calls) == 144
        assert len(second_adapter.calls) == 0
    finally:
        authorization.unlink(missing_ok=True)
        v6.OUTPUT.unlink(missing_ok=True)
