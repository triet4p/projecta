#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Concrete no-retry provider boundary for the prepared S12-f-12 stages."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from sprint12_provider_adapter import (
    ProviderAdapterError,
    ProviderCapture,
    ResponsesTransport,
    UrllibChatCompletionsTransport,
    _extract_message_content,
    _usage,
)

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-m3-prompt-v7-v2-two-step-extraction.v1.txt"
SCHEMA1 = ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-1-entity-envelope.schema.v2.json"
SCHEMA2 = ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-2-relation-envelope.schema.v2.json"
MODEL = "deepseek-v4-flash"
PROMPT_VERSION = "m3.prompt.v7-v2.two-step-extraction"
EXPECTED_CALLS = 144


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class F12RuntimeConfiguration:
    base_url: str
    api_key: str = field(default="", repr=False, compare=False)
    model: str = MODEL
    prompt_version: str = PROMPT_VERSION
    prompt_digest: str = ""
    stage1_schema_digest: str = ""
    stage2_schema_digest: str = ""
    timeout_seconds: float = 60.0
    max_output_tokens: int = 4096
    max_input_tokens_per_call: int = 50000
    temperature: float = 0.0
    top_p: float = 1.0
    retry_policy: str = "none"
    expected_provider_calls: int = EXPECTED_CALLS

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> F12RuntimeConfiguration:
        values = dict(os.environ)
        if environment is not None:
            values.update(environment)
        if values.get("PROJECTA_LLM_TYPE") != "openai-response":
            raise ProviderAdapterError("PROJECTA_LLM_TYPE is not the bound provider type")
        base_url = values.get("PROJECTA_LLM_BASE_URL", "")
        if not base_url.startswith(("https://", "http://")):
            raise ProviderAdapterError("PROJECTA_LLM_BASE_URL must be HTTP(S)")
        if not values.get("PROJECTA_LLM_API_KEY"):
            raise ProviderAdapterError("PROJECTA_LLM_API_KEY is not configured")
        if values.get("PROJECTA_LLM_MODEL") != MODEL:
            raise ProviderAdapterError("PROJECTA_LLM_MODEL is not deepseek-v4-flash")
        return cls(
            base_url=base_url.rstrip("/"),
            api_key=values["PROJECTA_LLM_API_KEY"],
            prompt_digest=_digest(PROMPT),
            stage1_schema_digest=_digest(SCHEMA1),
            stage2_schema_digest=_digest(SCHEMA2),
        )

    def sanitized(self) -> dict[str, object]:
        return {
            "model": self.model,
            "promptVersion": self.prompt_version,
            "promptPath": PROMPT.relative_to(ROOT).as_posix(),
            "promptDigest": self.prompt_digest,
            "stage1SchemaPath": SCHEMA1.relative_to(ROOT).as_posix(),
            "stage1SchemaDigest": self.stage1_schema_digest,
            "stage2SchemaPath": SCHEMA2.relative_to(ROOT).as_posix(),
            "stage2SchemaDigest": self.stage2_schema_digest,
            "timeoutSeconds": self.timeout_seconds,
            "maxOutputTokens": self.max_output_tokens,
            "maxInputTokensPerCall": self.max_input_tokens_per_call,
            "temperature": self.temperature,
            "topP": self.top_p,
            "retryPolicy": self.retry_policy,
            "expectedProviderCalls": self.expected_provider_calls,
        }

    @property
    def digest(self) -> str:
        return _canonical(self.sanitized())

    @property
    def worst_case_cost_usd(self) -> str:
        value = self.expected_provider_calls * (
            self.max_input_tokens_per_call * 0.14 / 1_000_000
            + self.max_output_tokens * 0.28 / 1_000_000
        )
        return f"{value:.8f}"


class F12ProviderAdapter:
    """Digestable stage-aware adapter; capture has exactly one transport call."""

    def __init__(
        self,
        configuration: F12RuntimeConfiguration,
        *,
        transport: ResponsesTransport | None = None,
    ) -> None:
        if configuration.retry_policy != "none" or configuration.model != MODEL:
            raise ProviderAdapterError("f12 adapter binding is not canonical")
        if _digest(PROMPT) != configuration.prompt_digest:
            raise ProviderAdapterError("prompt digest mismatch")
        if _digest(SCHEMA1) != configuration.stage1_schema_digest:
            raise ProviderAdapterError("stage-1 schema digest mismatch")
        if _digest(SCHEMA2) != configuration.stage2_schema_digest:
            raise ProviderAdapterError("stage-2 schema digest mismatch")
        self.configuration = configuration
        self._transport = transport or UrllibChatCompletionsTransport()
        self._prompt = PROMPT.read_text(encoding="utf-8")
        self._schemas = {
            "stage1": json.loads(SCHEMA1.read_text(encoding="utf-8")),
            "stage2": json.loads(SCHEMA2.read_text(encoding="utf-8")),
        }

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        transport: ResponsesTransport | None = None,
    ) -> F12ProviderAdapter:
        return cls(F12RuntimeConfiguration.from_environment(environment), transport=transport)

    @property
    def adapter_digest(self) -> str:
        return _digest(Path(__file__).resolve())

    @property
    def runtime_configuration_digest(self) -> str:
        return self.configuration.digest

    def capture_stage(
        self,
        *,
        stage: str,
        case_id: str,
        run_id: str,
        raw_text: str,
    ) -> ProviderCapture:
        if stage not in self._schemas:
            raise ProviderAdapterError("unknown f12 stage")
        if not case_id or not run_id or not raw_text:
            raise ProviderAdapterError("case, run and source context are required")
        schema = self._schemas[stage]
        schema_name = str(schema["$id"])
        payload = {
            "model": self.configuration.model,
            "messages": [
                {"role": "system", "content": f"{self._prompt}\nExact JSON Schema:\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}"},
                {"role": "user", "content": raw_text},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.configuration.max_output_tokens,
            "temperature": self.configuration.temperature,
            "top_p": self.configuration.top_p,
            "thinking": {"type": "disabled"},
            "metadata": {"stage": stage, "caseId": case_id, "runId": run_id, "schema": schema_name},
        }
        response = self._transport.post(
            url=self.configuration.base_url,
            api_key=self.configuration.api_key,
            payload=payload,
            timeout_seconds=self.configuration.timeout_seconds,
        )
        content = _extract_message_content(response)
        try:
            decoded = json.loads(content)
        except (TypeError, json.JSONDecodeError) as error:
            raise ProviderAdapterError("provider returned non-JSON stage output") from error
        if not isinstance(decoded, dict):
            raise ProviderAdapterError("provider stage output is not an object")
        usage = _usage(response.get("usage"))
        if usage["inputTokens"] > self.configuration.max_input_tokens_per_call:
            raise ProviderAdapterError("input token bound exceeded")
        if usage["outputTokens"] > self.configuration.max_output_tokens:
            raise ProviderAdapterError("output token bound exceeded")
        return ProviderCapture(payload=decoded, usage=usage, retry_count=0)
