from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from preflight_sprint12_f12_rm22b import REQUIRED_SLICE_LABELS, run_preflight
from run_sprint12_f12_stage_a_v3 import (
    FREEZE,
    PACKAGE,
    digest,
    run_stage_a,
)
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


def _authorization(path: Path, *, commit_sha: str | None = None) -> Path:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    target = (
        ROOT
        / "evaluation/sprint-12/optimization/.s12-f-12-rm22b-test-authorization.json"
    )
    target.write_text(
        json.dumps(
            {
                "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
                "experimentId": "s12-f-12",
                "providerExecutionAuthorized": True,
                "providerCalls": 144,
                "retryPolicy": "none",
                "commitSha": commit_sha or package["commitSha"],
                "executionPackage": {"digest": digest(PACKAGE)},
                "freezeRecord": {"digest": digest(FREEZE)},
                "outputPath": path.relative_to(ROOT).as_posix(),
                "costCeilingUsd": "10.00",
            }
        ),
        encoding="utf-8",
    )
    return target


def test_rm22b_preflight_is_zero_call_and_denominators_are_not_tripled() -> None:
    result = run_preflight()
    assert result["status"] == "F12_RM22B_READY_ZERO_CALL_V3"
    assert result["derivedDenominators"]["relationInstancesAcrossRuns"] == 24
    assert result["derivedDenominators"]["abstentionInstancesAcrossRuns"] == 12
    assert result["providerCalls"] == 0


def test_mock_authorized_v3_run_emits_all_slices_and_rejects_low_quality() -> None:
    output = (
        ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.test.v3.json"
    )
    authorization = _authorization(output)
    adapter = MockStageAdapter()
    try:
        report = run_stage_a(
            provider_adapter=adapter,
            authorization_path=authorization,
            output_path=output,
        )
        assert len(adapter.calls) == 144
        assert report["accounting"]["denominators"] == {
            "caseRuns": 48,
            "relationInstances": 24,
            "abstentionInstances": 12,
        }
        assert [
            item["label"] for item in report["sliceRecords"]
        ] == list(REQUIRED_SLICE_LABELS)
        assert report["decision"]["status"] == "COMPLETED_REJECTED_HARD_GATE"
        assert report["metrics"]["hardGates"]["sharedConfigurationMismatch"] == 0
    finally:
        output.unlink(missing_ok=True)
        authorization.unlink(missing_ok=True)


def test_wrong_exact_commit_is_rejected_before_capture() -> None:
    output = (
        ROOT
        / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.commit-test.v3.json"
    )
    authorization = _authorization(output, commit_sha="0" * 40)
    adapter = MockStageAdapter()
    try:
        with pytest.raises(RuntimeError, match="exact freeze commit"):
            run_stage_a(
                provider_adapter=adapter,
                authorization_path=authorization,
                output_path=output,
            )
        assert adapter.calls == []
    finally:
        output.unlink(missing_ok=True)
        authorization.unlink(missing_ok=True)
