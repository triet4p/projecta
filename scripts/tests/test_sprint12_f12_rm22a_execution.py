from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from preflight_sprint12_f12_rm22a import derive_denominators
from run_sprint12_f12_stage_a_v2 import FREEZE, PACKAGE, digest, run_stage_a
from sprint12_f12_provider_adapter import (
    PROMPT,
    SCHEMA1,
    SCHEMA2,
    F12RuntimeConfiguration,
    ProviderCapture,
)
from sprint12_f12_provider_adapter_v2 import F12ProviderAdapterV2


class MockStageAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def capture_stage(self, **kwargs: object) -> ProviderCapture:
        self.calls.append(kwargs)
        stage = kwargs["stage"]
        if stage == "stage1":
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


class MockTransport:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def post(
        self,
        *,
        url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        self.payloads.append(payload)
        metadata = payload["messages"][-1]["content"]
        context = json.loads(str(metadata))
        if context["stage"] == "stage1":
            content = {
                "schemaVersion": "s12-f-12.stage1.entity-envelope.v2",
                "entities": [],
                "abstention": {"required": True, "reason": "mock"},
            }
        else:
            content = {
                "schemaVersion": "s12-f-12.stage2.relation-envelope.v2",
                "relations": [],
                "abstention": {"required": True, "reason": "mock"},
            }
        return {
            "choices": [
                {"message": {"content": json.dumps(content)}, "finish_reason": "stop"}
            ],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 100,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 1000,
            },
        }


def _authorization(output_path: Path) -> Path:
    path = (
        ROOT
        / "evaluation/sprint-12/optimization/.s12-f-12-rm22a-test-authorization.json"
    )
    value = {
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "experimentId": "s12-f-12",
        "providerExecutionAuthorized": True,
        "providerCalls": 144,
        "retryPolicy": "none",
        "executionPackage": {"digest": digest(PACKAGE)},
        "freezeRecord": {"digest": digest(FREEZE)},
        "outputPath": output_path.relative_to(ROOT).as_posix(),
        "costCeilingUsd": "10.00",
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_mock_authorized_e2e_executes_exactly_144_calls_and_persists_once() -> None:
    output = (
        ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.test.json"
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
        assert report["accounting"]["providerCallsAttempted"] == 144
        assert report["accounting"]["retryCount"] == 0
        assert report["accounting"]["pricedCalls"] == 144
        assert report["custody"]["rawSourceTextStored"] is False
        assert report["custody"]["rawProviderPayloadStored"] is False
        assert output.exists()
        assert report["caseRecords"]
    finally:
        output.unlink(missing_ok=True)
        authorization.unlink(missing_ok=True)


def test_stage2_request_requires_and_serializes_candidate_table() -> None:
    transport = MockTransport()
    config = F12RuntimeConfiguration(
        base_url="https://example.invalid",
        api_key="test",
        prompt_digest=digest(PROMPT),
        stage1_schema_digest=digest(SCHEMA1),
        stage2_schema_digest=digest(SCHEMA2),
    )
    adapter = F12ProviderAdapterV2(config, transport=transport)
    adapter.capture_stage(
        stage="stage1",
        case_id="case",
        run_id="run-1",
        raw_text="source",
        arm="predicted-entities",
    )
    table = [
        {
            "candidateId": "gold-entity-01",
            "type": "Task",
            "startOffset": 0,
            "endOffset": 6,
            "confidence": 1.0,
        }
    ]
    adapter.capture_stage(
        stage="stage2",
        case_id="case",
        run_id="run-1",
        raw_text="source",
        arm="predicted-entities",
        candidate_table=[],
    )
    adapter.capture_stage(
        stage="stage2",
        case_id="case",
        run_id="run-1",
        raw_text="source",
        arm="gold-entities",
        candidate_table=table,
    )
    stage1_context = json.loads(str(transport.payloads[0]["messages"][-1]["content"]))
    predicted_context = json.loads(
        str(transport.payloads[1]["messages"][-1]["content"])
    )
    gold_context = json.loads(str(transport.payloads[2]["messages"][-1]["content"]))
    assert stage1_context["candidateTable"] is None
    assert predicted_context["candidateTable"] == []
    assert gold_context["candidateTable"] == table
    with pytest.raises(Exception, match="candidate table"):
        adapter.capture_stage(
            stage="stage1",
            case_id="case",
            run_id="run-1",
            raw_text="source",
            arm="predicted-entities",
            candidate_table=table,
        )


def test_denominators_are_derived_from_frozen_gold() -> None:
    derived = derive_denominators()
    assert derived["selectedDevelopmentCases"] == 16
    assert derived["positiveRelationCases"] == 8
    assert derived["goldRelationInstancesPerRun"] == 8
    assert derived["abstentionRequiredCases"] == 4
    assert derived["namedSliceDenominators"]["language"] == {
        "en": 6,
        "ja": 6,
        "mixed": 30,
        "vi": 6,
    }


def test_report_schema_declares_nonempty_execution_fields() -> None:
    schema = json.loads(
        (
            ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v2.json"
        ).read_text(encoding="utf-8")
    )
    accounting = schema["properties"]["accounting"]
    assert {
        "providerCallsAttempted",
        "responsesReceived",
        "pricedCalls",
        "totalCostUsd",
    } <= set(accounting["required"])
    assert "caseRecord" in schema["$defs"]
    assert "sliceRecord" in schema["$defs"]
