"""Contract tests for the final S12-f-10 preauthorization preflight."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "apps" / "api" / "src")]

from preflight_sprint12_f10_preauthorization import build_preflight
from run_sprint12_next_tool_experiment import (
    FINAL_FREEZE,
    FINAL_PACKAGE,
    ExecutionPackageError,
    _metric_summary,
    run_offline_stage_a,
    validate_final_execution_package,
)
from sprint12_evaluator import score_extraction
from sprint12_pricing import file_digest
from sprint12_provider_adapter import CallableProviderAdapter, ProviderCapture


def test_final_package_is_implemented_and_preflight_keeps_authorization_closed() -> None:
    package = validate_final_execution_package()
    assert package["executionRunnerImplemented"] is True
    report = build_preflight(run_tests=False)
    assert report["status"] == "NO_GO_PREAUTHORIZATION_PREFLIGHT"
    assert report["checks"]["packageStatus"] is True
    assert report["checks"]["providerSchemasMatch"] is True
    assert report["checks"]["caseSelectionReproducible"] is True
    assert report["checks"]["commitPresentInHead"] is True
    assert report["checks"]["allBoundFilesInCommit"] is True
    assert report["checks"]["canonicalTestsPass"] is False
    assert report["providerExecutionAuthorized"] is False


def _authorization(output: Path) -> Path:
    path = output.parent / "authorization.json"
    payload = {
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "providerExecutionAuthorized": True,
        "experimentId": "s12-f-10",
        "heldOutInspected": False,
        "retryPolicy": "none",
        "executionPackage": {"digest": file_digest(FINAL_PACKAGE)},
        "freezeRecord": {
            "path": str(FINAL_FREEZE.relative_to(ROOT).as_posix()),
            "digest": file_digest(FINAL_FREEZE),
        },
        "commitSha": "89680a4",
        "outputPath": str(output.resolve()),
        "costCeilingUsd": "10.00",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _payload(*, input_tokens: int = 0, output_tokens: int = 0) -> dict:
    return {
        "schemaVersion": "relation-evidence-envelope.v1",
        "extraction": {
            "schemaVersion": "m3.v2",
            "modelId": "offline",
            "modelVersion": "test",
            "entities": [],
            "relations": [],
            "links": [],
            "abstentionReason": "offline",
            "usage": {
                "inputTokens": input_tokens,
                "promptCacheHitTokens": 0,
                "promptCacheMissTokens": input_tokens,
                "outputTokens": output_tokens,
            },
        },
        "relationTriggers": [],
    }


def test_unauthorized_runner_makes_zero_adapter_calls(tmp_path: Path) -> None:
    calls: list[str] = []
    adapter = CallableProviderAdapter(
        lambda **kwargs: calls.append(str(kwargs["case_id"]))
        or ProviderCapture(payload=_payload())
    )

    with pytest.raises(ExecutionPackageError, match="Approval-B"):
        run_offline_stage_a(provider_adapter=adapter, output_path=tmp_path / "report.json")
    assert calls == []


def test_offline_runner_uses_48_captures_and_96_sanitized_branches(tmp_path: Path) -> None:
    calls: list[str] = []
    adapter = CallableProviderAdapter(
        lambda **kwargs: calls.append(str(kwargs["case_id"]))
        or ProviderCapture(
            payload=_payload(),
            usage={"inputTokens": 0, "promptCacheHitTokens": 0, "promptCacheMissTokens": 0, "outputTokens": 0},
        )
    )
    output = tmp_path / "stage-a-report.json"
    report = run_offline_stage_a(
        provider_adapter=adapter,
        authorization_path=_authorization(output),
        output_path=output,
    )

    assert len(calls) == 48
    assert report["providerCallCount"] == 48
    assert report["branchOutputCount"] == 96
    assert report["rawSensitiveDataIncluded"] is False
    assert output.exists()
    try:
        run_offline_stage_a(
            provider_adapter=adapter,
            authorization_path=_authorization(output),
            output_path=output,
        )
    except ExecutionPackageError as error:
        assert "overwrite" in str(error)
    else:
        raise AssertionError("runner must refuse to overwrite a sanitized report")


def test_metric_summary_counts_wrong_span_semantically_and_hard_negative_false_positive() -> None:
    gold_relation = {
        "predicate": "implements",
        "sourceEntityId": "task-1",
        "targetEntityId": "req-1",
        "span": {"start": 0, "end": 31},
    }
    gold = {
        "entities": [
            {"id": "task-1", "type": "Task", "span": {"start": 0, "end": 4}},
            {"id": "req-1", "type": "Requirement", "span": {"start": 19, "end": 31}},
        ],
        "relations": [gold_relation],
        "links": [],
        "abstention": {"required": False},
    }
    wrong_span = {
        "entities": gold["entities"],
        "relations": [{**gold_relation, "span": {"start": 5, "end": 18}}],
        "links": [],
        "abstention": {"required": False},
    }
    hard_negative = {
        "entities": [],
        "relations": [{"predicate": "supports", "span": {"start": 0, "end": 1}}],
        "links": [],
        "abstention": {"required": False},
    }
    summary = _metric_summary(
        [
            {"score": score_extraction(gold, wrong_span), "goldAbstention": False, "predictedAbstention": False, "labels": []},
            {"score": score_extraction({**gold, "relations": []}, hard_negative), "goldAbstention": False, "predictedAbstention": False, "labels": []},
        ]
    )
    assert summary["denominators"]["relationGold"] == 1
    assert summary["denominators"]["relationPredicted"] == 2
    assert summary["denominators"]["relationSemanticTruePositive"] == 1
    assert summary["relationSemanticMicroF1"] == pytest.approx(2 / 3)
    assert summary["relationEvidenceSupport"] == 0.0


def test_invalid_envelope_usage_is_priced_and_mirrored(tmp_path: Path) -> None:
    output = tmp_path / "invalid.json"
    adapter = CallableProviderAdapter(
        lambda **_kwargs: ProviderCapture(
            payload={"invalid": True},
            usage={"inputTokens": 10, "promptCacheHitTokens": 0, "promptCacheMissTokens": 10, "outputTokens": 5},
        )
    )
    report = run_offline_stage_a(
        provider_adapter=adapter,
        authorization_path=_authorization(output),
        output_path=output,
    )
    assert report["failureCounts"]["schema_invalid"] == 96
    assert report["pricing"]["providerCallsPriced"] == 48
    assert report["pricing"]["pricingFailures"] == 0
    assert report["hardGates"]["schemaFailures"] is False


def test_provider_failure_fails_closed_without_retry(tmp_path: Path) -> None:
    output = tmp_path / "timeout.json"
    adapter = CallableProviderAdapter(lambda **_kwargs: (_ for _ in ()).throw(TimeoutError("timeout")))
    report = run_offline_stage_a(
        provider_adapter=adapter,
        authorization_path=_authorization(output),
        output_path=output,
    )
    assert report["providerCallCount"] == 48
    assert report["failureCounts"]["provider_failure"] == 96
    assert report["retryCount"] == 0
    assert report["hardGates"]["pricing"] is False


def test_retry_count_is_a_hard_gate(tmp_path: Path) -> None:
    output = tmp_path / "retry.json"
    adapter = CallableProviderAdapter(
        lambda **_kwargs: ProviderCapture(payload=_payload(), retry_count=1)
    )
    report = run_offline_stage_a(
        provider_adapter=adapter,
        authorization_path=_authorization(output),
        output_path=output,
    )
    assert report["retryCount"] == 48
    assert report["hardGates"]["retryCount"] is False
