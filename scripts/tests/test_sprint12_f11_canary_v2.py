"""Offline tests for the superseding S12-f-11 canary lineage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

import run_sprint12_f11_canary_v2 as canary
from projecta_api.extraction.relation_evidence_envelope import (
    RelationEvidenceEnvelopeV1,
)

PROMPT_PATH = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-11-m3-prompt-v7-relation-trigger-envelope-examples.v2.txt"
)


class _MockTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        *,
        url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        self.calls.append(payload)
        return self.response


def _valid_payload() -> dict[str, object]:
    return {
        "schemaVersion": "relation-evidence-envelope.v1",
        "extraction": {
            "schemaVersion": "m3.v2",
            "modelId": "deepseek-v4-flash",
            "modelVersion": "deepseek-v4-flash",
            "entities": [],
            "relations": [],
            "links": [],
            "abstentionReason": "No ontology-grounded extraction is supported by the source.",
        },
        "relationTriggers": [],
    }


def _environment() -> dict[str, str]:
    return {
        "PROJECTA_LLM_TYPE": "openai-response",
        "PROJECTA_LLM_BASE_URL": "https://mock.invalid",
        "PROJECTA_LLM_API_KEY": "test-only",
        "PROJECTA_LLM_MODEL": "deepseek-v4-flash",
    }


def _provider_response(
    payload: dict[str, object], *, usage: dict[str, int] | None = None
) -> dict[str, object]:
    return {
        "choices": [
            {"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}
        ],
        "usage": usage
        or {
            "prompt_tokens": 12,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 12,
            "completion_tokens": 8,
        },
    }


def test_prompt_positive_example_materializes_against_its_source() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    source = "The checkout task implements the PCI requirement."
    output_shape = prompt.split("Output shape:\n", 1)[1]
    payload, _ = json.JSONDecoder().raw_decode(output_shape)
    envelope = RelationEvidenceEnvelopeV1.model_validate(payload)
    for entity in envelope.extraction.entities:
        evidence = entity.evidence
        assert source[evidence.start_offset : evidence.end_offset] == evidence.text
    relation = envelope.extraction.relations[0]
    assert (
        source[relation.evidence.start_offset : relation.evidence.end_offset]
        == relation.evidence.text
    )
    assert (relation.evidence.start_offset, relation.evidence.end_offset) == (4, 48)


def test_adapter_runtime_is_four_call_and_cost_bound() -> None:
    transport = _MockTransport(_provider_response(_valid_payload()))
    adapter = canary.build_canary_adapter(_environment(), transport=transport)
    assert adapter.configuration.expected_provider_calls == 4
    assert adapter.configuration.worst_case_cost_usd == pytest.approx(0.03258752)


def test_diagnostic_hashes_unknown_keys_and_paths() -> None:
    secret_key = "source-derived secret text"
    payload = {
        "schemaVersion": "relation-evidence-envelope.v1",
        secret_key: "never persist",
    }
    with pytest.raises(ValueError) as raised:
        RelationEvidenceEnvelopeV1.model_validate(payload)
    diagnostic = canary.schema_failure_diagnostic(payload, raised.value)
    serialized = json.dumps(diagnostic)
    assert secret_key not in serialized
    assert any(
        str(item).startswith("key:sha256:")
        for item in diagnostic["topLevelKeySignature"]
    )
    assert all(secret_key not in json.dumps(item) for item in diagnostic["errors"])


def test_accounting_separates_success_counters_with_mock_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transport = _MockTransport(_provider_response(_valid_payload()))
    adapter = canary.build_canary_adapter(_environment(), transport=transport)
    monkeypatch.setattr(
        canary,
        "validate_canary_authorization",
        lambda *args, **kwargs: {"costCeilingUsd": "10.00"},
    )
    report = canary.run_canary(
        provider_adapter=adapter,
        authorization_path=tmp_path / "mock-authorization.json",
        output_path=tmp_path / "report.json",
    )
    assert len(transport.calls) == 4
    assert report["providerCallsAttempted"] == 4
    assert report["responsesReceived"] == 4
    assert report["schemaValidResponses"] == 4
    assert report["usageValidResponses"] == 4
    assert report["providerCallsPriced"] == 4
    assert report["failureCounts"] == {}


def test_accounting_does_not_call_usage_failure_schema_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_usage = _MockTransport(_provider_response(_valid_payload(), usage=None))
    # Force a response with no usage field; the concrete adapter rejects it at the provider boundary.
    missing_usage.response.pop("usage")
    adapter = canary.build_canary_adapter(_environment(), transport=missing_usage)
    monkeypatch.setattr(
        canary,
        "validate_canary_authorization",
        lambda *args, **kwargs: {"costCeilingUsd": "10.00"},
    )
    report = canary.run_canary(
        provider_adapter=adapter,
        authorization_path=tmp_path / "mock-authorization.json",
        output_path=tmp_path / "report.json",
    )
    assert report["providerCallsAttempted"] == 4
    assert report["responsesReceived"] == 0
    assert report["schemaValidResponses"] == 0
    assert report["usageValidResponses"] == 0
    assert report["providerCallsPriced"] == 0
    assert report["failureCounts"] == {"usage_invalid": 4}
