"""Offline parity and sanitized-diagnostic tests for S12-f-11."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from projecta_api.extraction.relation_evidence_envelope import (
    RelationEvidenceEnvelopeV1,
)
from run_sprint12_f11_canary import (
    CanaryExecutionError,
    build_canary_adapter,
    run_canary,
    schema_failure_diagnostic,
)
from sprint12_provider_adapter import ProviderCapture

SCHEMA_PATH = (
    ROOT / "evaluation/sprint-12/harness/relation-evidence-envelope.schema.v2.json"
)


def test_schema_v2_matches_pydantic_nested_definitions_and_is_strict() -> None:
    artifact = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    generated = RelationEvidenceEnvelopeV1.model_json_schema(by_alias=True)

    expected_defs = json.loads(json.dumps(generated["$defs"]))
    expected_defs["ExtractionResponse"]["required"] = [
        "schemaVersion",
        "modelId",
        "modelVersion",
        "entities",
        "relations",
        "links",
    ]
    assert artifact["$defs"] == expected_defs
    assert artifact["required"] == ["schemaVersion", "extraction", "relationTriggers"]
    assert artifact["$defs"]["ExtractionResponse"]["required"] == [
        "schemaVersion",
        "modelId",
        "modelVersion",
        "entities",
        "relations",
        "links",
    ]
    assert artifact["$defs"]["ExtractionResponse"]["properties"]["entities"][
        "items"
    ] == {"$ref": "#/$defs/EntityCandidateOutput"}
    assert artifact["$defs"]["ExtractionResponse"]["properties"]["relations"][
        "items"
    ] == {"$ref": "#/$defs/RelationCandidateOutput"}
    assert artifact["$defs"]["ExtractionResponse"]["properties"]["links"]["items"] == {
        "$ref": "#/$defs/EntityLinkCandidateOutput"
    }
    for definition in artifact["$defs"].values():
        if definition.get("type") == "object":
            assert definition.get("additionalProperties") is False


def test_pydantic_accepts_prompt_positive_example_shape() -> None:
    envelope = RelationEvidenceEnvelopeV1.model_validate(
        {
            "schemaVersion": "relation-evidence-envelope.v1",
            "extraction": {
                "schemaVersion": "m3.v2",
                "modelId": "deepseek-v4-flash",
                "modelVersion": "deepseek-v4-flash",
                "entities": [
                    {
                        "candidateId": "task-1",
                        "type": "Task",
                        "label": "checkout task",
                        "evidence": {
                            "startOffset": 4,
                            "endOffset": 18,
                            "text": "checkout task",
                        },
                        "confidence": 0.99,
                    },
                    {
                        "candidateId": "req-1",
                        "type": "Requirement",
                        "label": "PCI requirement",
                        "evidence": {
                            "startOffset": 38,
                            "endOffset": 53,
                            "text": "PCI requirement",
                        },
                        "confidence": 0.99,
                    },
                ],
                "relations": [
                    {
                        "predicate": "implements",
                        "sourceEntityId": "task-1",
                        "targetEntityId": "req-1",
                        "evidence": {
                            "startOffset": 4,
                            "endOffset": 53,
                            "text": "checkout task implements the PCI requirement",
                        },
                        "confidence": 0.98,
                    }
                ],
                "links": [],
                "abstentionReason": None,
            },
            "relationTriggers": [
                {
                    "predicate": "implements",
                    "sourceEntityId": "task-1",
                    "targetEntityId": "req-1",
                    "triggerQuote": "implements",
                }
            ],
        }
    )
    assert envelope.extraction.relations[0].source_entity_id == "task-1"


def test_schema_diagnostic_contains_structure_only() -> None:
    payload = {
        "schemaVersion": "relation-evidence-envelope.v1",
        "sourceText": "do-not-persist-this-source",
        "extraction": {
            "schemaVersion": "m3.v2",
            "modelId": "deepseek-v4-flash",
            "modelVersion": "deepseek-v4-flash",
            "entities": [{"candidateId": "task-1"}],
            "relations": [],
            "links": [],
        },
        "relationTriggers": [],
    }
    with pytest.raises(ValueError) as raised:
        RelationEvidenceEnvelopeV1.model_validate(payload)

    diagnostic = schema_failure_diagnostic(payload, raised.value)
    serialized = json.dumps(diagnostic, ensure_ascii=False)
    assert diagnostic["topLevelKeySignature"] == [
        "extraction",
        "relationTriggers",
        "schemaVersion",
        "sourceText",
    ]
    assert diagnostic["arrayCounts"] == {
        "extraction.entities": 1,
        "extraction.links": 0,
        "extraction.relations": 0,
        "relationTriggers": 0,
    }
    assert "do-not-persist-this-source" not in serialized
    assert "source text" not in serialized.lower()
    assert all(set(item) == {"type", "path"} for item in diagnostic["errors"])


class _MockTransport:
    def __init__(self, content: dict[str, object]) -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        *,
        url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "url": url,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "choices": [
                {
                    "message": {"content": json.dumps(self.content)},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 12,
                "completion_tokens": 8,
            },
        }


def _valid_provider_payload() -> dict[str, object]:
    return {
        "schemaVersion": "relation-evidence-envelope.v1",
        "extraction": {
            "schemaVersion": "m3.v2",
            "modelId": "deepseek-v4-flash",
            "modelVersion": "deepseek-v4-flash",
            "entities": [
                {
                    "candidateId": "task-1",
                    "type": "Task",
                    "label": "checkout task",
                    "evidence": {
                        "startOffset": 0,
                        "endOffset": 13,
                        "text": "checkout task",
                    },
                    "confidence": 0.99,
                },
                {
                    "candidateId": "req-1",
                    "type": "Requirement",
                    "label": "PCI requirement",
                    "evidence": {
                        "startOffset": 18,
                        "endOffset": 33,
                        "text": "PCI requirement",
                    },
                    "confidence": 0.99,
                },
            ],
            "relations": [
                {
                    "predicate": "implements",
                    "sourceEntityId": "task-1",
                    "targetEntityId": "req-1",
                    "evidence": {
                        "startOffset": 0,
                        "endOffset": 33,
                        "text": "checkout task implements PCI requirement",
                    },
                    "confidence": 0.98,
                }
            ],
            "links": [],
            "abstentionReason": None,
        },
        "relationTriggers": [
            {
                "predicate": "implements",
                "sourceEntityId": "task-1",
                "targetEntityId": "req-1",
                "triggerQuote": "implements",
            }
        ],
    }


def test_mock_transport_receives_f11_binding_once() -> None:
    transport = _MockTransport(_valid_provider_payload())
    adapter = build_canary_adapter(
        {
            "PROJECTA_LLM_TYPE": "openai-response",
            "PROJECTA_LLM_BASE_URL": "https://mock.invalid",
            "PROJECTA_LLM_API_KEY": "test-only",
            "PROJECTA_LLM_MODEL": "deepseek-v4-flash",
        },
        transport=transport,
    )

    capture = adapter.capture(
        case_id="s12-a-test",
        raw_text="checkout task implements PCI requirement",
        prompt_version="m3.prompt.v7.relation-trigger-envelope-examples",
        provider_schema="relation-evidence-envelope.v1",
    )

    assert isinstance(capture, ProviderCapture)
    assert len(transport.calls) == 1
    request = transport.calls[0]["payload"]
    assert request["model"] == "deepseek-v4-flash"
    assert request["response_format"] == {"type": "json_object"}
    assert request["max_tokens"] == 4096
    assert request["temperature"] == 0.0
    assert request["top_p"] == 1.0
    assert (
        "s12.relation-evidence-envelope.schema.v2" in request["messages"][0]["content"]
    )
    assert capture.retry_count == 0


def test_canary_rejects_missing_authorization_before_transport(tmp_path: Path) -> None:
    transport = _MockTransport(_valid_provider_payload())
    adapter = build_canary_adapter(
        {
            "PROJECTA_LLM_TYPE": "openai-response",
            "PROJECTA_LLM_BASE_URL": "https://mock.invalid",
            "PROJECTA_LLM_API_KEY": "test-only",
            "PROJECTA_LLM_MODEL": "deepseek-v4-flash",
        },
        transport=transport,
    )

    with pytest.raises(CanaryExecutionError, match="separate f11 canary authorization"):
        run_canary(
            provider_adapter=adapter,
            authorization_path=None,
            output_path=tmp_path / "canary-report.json",
        )
    assert transport.calls == []
