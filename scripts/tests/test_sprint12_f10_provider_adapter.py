"""Tests for the concrete S12-f-10 provider boundary using mock transport."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprint12_provider_adapter import (
    DeepSeekProviderAdapter,
    DeepSeekRuntimeConfiguration,
    ProviderAdapterError,
)


class MockTransport:
    def __init__(self, response: Mapping[str, object] | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.response = response or {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"schemaVersion":"relation-evidence-envelope.v1","extraction":{"schemaVersion":"m3.v2","modelId":"deepseek-v4-flash","modelVersion":"deepseek-v4-flash","entities":[],"relations":[],"links":[]},"relationTriggers":[]}'
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "prompt_cache_hit_tokens": 10,
                "prompt_cache_miss_tokens": 90,
                "completion_tokens": 20,
            },
        }

    def post(
        self,
        *,
        url: str,
        api_key: str,
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        self.calls.append(
            {
                "url": url,
                "api_key": api_key,
                "payload": dict(payload),
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        "PROJECTA_LLM_TYPE": "openai-response",
        "PROJECTA_LLM_BASE_URL": "https://api.deepseek.com",
        "PROJECTA_LLM_API_KEY": "test-secret",
        "PROJECTA_LLM_MODEL": "deepseek-v4-flash",
    }
    values.update(overrides)
    return values


def test_concrete_adapter_binds_request_model_prompt_schema_sampling_and_limits() -> (
    None
):
    transport = MockTransport()
    adapter = DeepSeekProviderAdapter.from_environment(
        _environment(), transport=transport
    )

    capture = adapter.capture(
        case_id="case-1",
        raw_text="A task implements a requirement.",
        prompt_version="m3.prompt.v6.relation-trigger-envelope",
        provider_schema="relation-evidence-envelope.v1",
    )

    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == "https://api.deepseek.com"
    assert call["api_key"] == "test-secret"
    assert call["timeout_seconds"] == 60.0
    payload = call["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "deepseek-v4-flash"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["max_tokens"] == 4096
    assert payload["temperature"] == 0.0
    assert payload["top_p"] == 1.0
    assert payload["thinking"] == {"type": "disabled"}
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert "m3.prompt.v6.relation-trigger-envelope" in messages[0]["content"]
    assert "relation-evidence-envelope.v1" in messages[0]["content"]
    assert messages[1] == {
        "role": "user",
        "content": "A task implements a requirement.",
    }
    assert capture.retry_count == 0
    assert capture.usage == {
        "inputTokens": 100,
        "promptCacheHitTokens": 10,
        "promptCacheMissTokens": 90,
        "outputTokens": 20,
    }


def test_binding_mutation_fails_before_transport_call() -> None:
    transport = MockTransport()
    configuration = DeepSeekRuntimeConfiguration.from_environment(_environment())
    mutated = replace(configuration, model="different-model")

    with pytest.raises(ProviderAdapterError, match="frozen DeepSeek model"):
        DeepSeekProviderAdapter(mutated, transport=transport)
    assert transport.calls == []


def test_runtime_digest_excludes_secret_but_changes_with_bound_runtime_values() -> None:
    first = DeepSeekRuntimeConfiguration.from_environment(
        _environment(PROJECTA_LLM_API_KEY="one")
    )
    second = DeepSeekRuntimeConfiguration.from_environment(
        _environment(PROJECTA_LLM_API_KEY="two")
    )
    changed_base_url = replace(first, base_url="https://different.example")

    assert first.digest == second.digest
    assert first.digest != changed_base_url.digest
    assert first.sanitized()["apiKeyConfigured"] is True


def test_provider_failure_is_not_retried() -> None:
    class FailingTransport(MockTransport):
        def post(self, **kwargs: object) -> Mapping[str, object]:
            self.calls.append(dict(kwargs))
            raise ProviderAdapterError("transport failure")

    transport = FailingTransport()
    adapter = DeepSeekProviderAdapter.from_environment(
        _environment(), transport=transport
    )
    with pytest.raises(ProviderAdapterError, match="transport failure"):
        adapter.capture(
            case_id="case-1",
            raw_text="source",
            prompt_version="m3.prompt.v6.relation-trigger-envelope",
            provider_schema="relation-evidence-envelope.v1",
        )
    assert len(transport.calls) == 1


def test_output_bound_is_fail_closed_after_one_request() -> None:
    transport = MockTransport(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "{}"},
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 1,
                "completion_tokens": 4097,
            },
        }
    )
    adapter = DeepSeekProviderAdapter.from_environment(
        _environment(), transport=transport
    )
    with pytest.raises(ProviderAdapterError, match="max_tokens"):
        adapter.capture(
            case_id="case-1",
            raw_text="source",
            prompt_version="m3.prompt.v6.relation-trigger-envelope",
            provider_schema="relation-evidence-envelope.v1",
        )
    assert len(transport.calls) == 1
