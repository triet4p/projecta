from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v5 as v5
from preflight_sprint12_f12_rm22d import run_preflight
from run_sprint12_f12_stage_a_v5 import (
    FREEZE,
    PACKAGE,
    digest,
    run_stage_a,
    validate_authorization,
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


def _authorization(path: Path, **changes: object) -> Path:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    target = ROOT / "evaluation/sprint-12/optimization/.s12-f-12-rm22d-test-authorization.json"
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
        "heldOutAccessAuthorized": False,
        "validationAccessAuthorized": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
    }
    payload.update(changes)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_rm22d_preflight_is_zero_call_and_binds_v5_lineage() -> None:
    result = run_preflight()
    assert result["status"] == "F12_RM22D_READY_ZERO_CALL_V5"
    assert result["providerCalls"] == 0
    assert result["derivedDenominators"]["namedSliceDenominators"]["relation-negative"] == 12


def test_rm22d_schema_rejects_slice_and_threshold_tampering() -> None:
    output = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.test.v5.json"
    authorization = _authorization(output)
    try:
        report = run_stage_a(
            provider_adapter=MockStageAdapter(),
            authorization_path=authorization,
            output_path=output,
        )
        for mutate in (
            lambda value: value["sliceRecords"][0].update({"label": "tampered"}),
            lambda value: value["sliceRecords"][0].update({"denominator": 999}),
            lambda value: value["metrics"]["thresholds"].update({"entityMacroF1Min": -999}),
        ):
            tampered = copy.deepcopy(report)
            mutate(tampered)
            with pytest.raises(RuntimeError, match="schema validation failed"):
                v5._validate_report_schema(tampered)
    finally:
        output.unlink(missing_ok=True)
        authorization.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "changes",
    [
        {"heldOutAccessAuthorized": True},
        {"validationAccessAuthorized": True},
        {"unexpectedAuthorizationField": True},
    ],
)
def test_rm22d_authorization_schema_rejects_expanded_or_unknown_scope(
    changes: dict[str, object],
) -> None:
    output = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.auth-test.v5.json"
    authorization = _authorization(output, **changes)
    try:
        with pytest.raises(RuntimeError, match="authorization schema validation failed"):
            validate_authorization(authorization, output_path=output)
    finally:
        output.unlink(missing_ok=True)
        authorization.unlink(missing_ok=True)
