from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from preflight_sprint12_f12_rm22c import run_preflight
from run_sprint12_f12_stage_a_v4 import FREEZE, PACKAGE, digest, run_stage_a
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


def _authorization(path: Path, *, include_selection_guard: bool = True) -> Path:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    target = ROOT / "evaluation/sprint-12/optimization/.s12-f-12-rm22c-test-authorization.json"
    payload: dict[str, object] = {
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "experimentId": "s12-f-12",
        "providerExecutionAuthorized": True,
        "providerCalls": 144,
        "retryPolicy": "none",
        "commitSha": package["commitSha"],
        "executionPackage": {"digest": digest(PACKAGE)},
        "freezeRecord": {"digest": digest(FREEZE)},
        "outputPath": path.relative_to(ROOT).as_posix(),
        "costCeilingUsd": "10.00",
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "promotionAuthorized": False,
    }
    if include_selection_guard:
        payload["candidateSelectionAuthorized"] = False
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_rm22c_preflight_separates_hard_negative_and_abstention_denominators() -> None:
    result = run_preflight()
    assert result["status"] == "F12_RM22C_READY_ZERO_CALL_V4"
    assert result["derivedDenominators"]["relationInstancesAcrossRuns"] == 24
    assert result["derivedDenominators"]["namedSliceDenominators"]["relation-negative"] == 12
    assert result["derivedDenominators"]["namedSliceDenominators"]["abstention-required"] == 12
    assert result["providerCalls"] == 0


def test_rm22c_mock_run_has_zero_gold_oracle_failures_and_applicable_slices() -> None:
    output = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.test.v4.json"
    authorization = _authorization(output)
    adapter = MockStageAdapter()
    try:
        report = run_stage_a(
            provider_adapter=adapter,
            authorization_path=authorization,
            output_path=output,
        )
        assert len(adapter.calls) == 144
        assert report["artifactVersion"] == "s12-f-12.stage-a-report.v4"
        assert report["metrics"]["goldRelationsMaterializerFailures"] == 0
        negative = next(item for item in report["sliceRecords"] if item["label"] == "relation-negative")
        abstention = next(item for item in report["sliceRecords"] if item["label"] == "abstention-required")
        assert negative["denominator"] == 12
        assert abstention["denominator"] == 12
        assert report["decision"]["status"] == "COMPLETED_REJECTED_HARD_GATE"
    finally:
        output.unlink(missing_ok=True)
        authorization.unlink(missing_ok=True)


def test_rm22c_authorization_requires_all_sealed_scope_guards() -> None:
    output = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.guard-test.v4.json"
    authorization = _authorization(output, include_selection_guard=False)
    adapter = MockStageAdapter()
    try:
        with pytest.raises(RuntimeError, match="sealed governance scope"):
            run_stage_a(
                provider_adapter=adapter,
                authorization_path=authorization,
                output_path=output,
            )
        assert adapter.calls == []
    finally:
        output.unlink(missing_ok=True)
        authorization.unlink(missing_ok=True)
