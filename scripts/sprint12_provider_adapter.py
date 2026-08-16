"""Provider boundary for the S12-f-10 shared-response runner.

The offline runner owns pairing, schema validation, scoring and report
custody. The concrete adapter below owns exactly one DeepSeek request per
case/run. Its configuration is immutable, its request is fully bound to the
frozen prompt/schema/model contract, and its transport is injectable so that
the live boundary can be tested without making a provider call.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

Usage = Mapping[str, int | None]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT_PATH = ROOT / (
    "evaluation/sprint-12/optimization/"
    "s12-f-10-m3-prompt-v6-relation-trigger-envelope.v1.txt"
)
DEFAULT_SCHEMA_PATH = ROOT / (
    "evaluation/sprint-12/harness/relation-evidence-envelope.schema.v1.json"
)
EXPECTED_PROVIDER_TYPE = "openai-response"
EXPECTED_MODEL = "deepseek-v4-flash"
EXPECTED_PROMPT_VERSION = "m3.prompt.v6.relation-trigger-envelope"
EXPECTED_PROVIDER_SCHEMA = "relation-evidence-envelope.v1"
EXPECTED_RETRY_POLICY = "none"
EXPECTED_CALLS = 48
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_MAX_INPUT_TOKENS_PER_CALL = 50_000
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TOP_P = 1.0


class ProviderAdapterError(RuntimeError):
    """Raised when the provider boundary cannot satisfy its frozen contract."""


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _file_digest(path: Path) -> str:
    return (
        "sha256:"
        + hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    )


@dataclass(frozen=True, slots=True)
class DeepSeekRuntimeConfiguration:
    """Non-secret runtime values which must be digest-bound by Approval B."""

    base_url: str
    model: str = EXPECTED_MODEL
    provider_type: str = EXPECTED_PROVIDER_TYPE
    prompt_version: str = EXPECTED_PROMPT_VERSION
    provider_schema: str = EXPECTED_PROVIDER_SCHEMA
    prompt_path: str = "evaluation/sprint-12/optimization/s12-f-10-m3-prompt-v6-relation-trigger-envelope.v1.txt"
    schema_path: str = (
        "evaluation/sprint-12/harness/relation-evidence-envelope.schema.v1.json"
    )
    prompt_digest: str = ""
    schema_digest: str = ""
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    max_input_tokens_per_call: int = DEFAULT_MAX_INPUT_TOKENS_PER_CALL
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P
    retry_policy: str = EXPECTED_RETRY_POLICY
    expected_provider_calls: int = EXPECTED_CALLS
    api_key: str = field(default="", repr=False, compare=False)

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        prompt_path: Path = DEFAULT_PROMPT_PATH,
        schema_path: Path = DEFAULT_SCHEMA_PATH,
    ) -> DeepSeekRuntimeConfiguration:
        values = dict(os.environ)
        if environment is not None:
            values.update(environment)
        provider_type = values.get("PROJECTA_LLM_TYPE", "")
        base_url = values.get("PROJECTA_LLM_BASE_URL", "")
        api_key = values.get("PROJECTA_LLM_API_KEY", "")
        model = values.get("PROJECTA_LLM_MODEL", "")
        if provider_type != EXPECTED_PROVIDER_TYPE:
            raise ProviderAdapterError(
                "PROJECTA_LLM_TYPE must be the bound openai-response configuration"
            )
        if not base_url.startswith(("https://", "http://")):
            raise ProviderAdapterError("PROJECTA_LLM_BASE_URL must be an HTTP(S) URL")
        if not api_key:
            raise ProviderAdapterError("PROJECTA_LLM_API_KEY is not configured")
        if model != EXPECTED_MODEL:
            raise ProviderAdapterError(
                "PROJECTA_LLM_MODEL does not match deepseek-v4-flash"
            )
        if not prompt_path.is_file() or not schema_path.is_file():
            raise ProviderAdapterError("frozen prompt or provider schema is missing")
        return cls(
            base_url=base_url.rstrip("/"),
            model=model,
            provider_type=provider_type,
            prompt_digest=_file_digest(prompt_path),
            schema_digest=_file_digest(schema_path),
            api_key=api_key,
        )

    def sanitized(self) -> dict[str, object]:
        """Return the exact non-secret configuration represented by the digest."""

        return {
            "baseUrl": self.base_url,
            "model": self.model,
            "providerType": self.provider_type,
            "transport": "deepseek-chat-completions",
            "promptVersion": self.prompt_version,
            "providerSchema": self.provider_schema,
            "promptPath": self.prompt_path,
            "promptDigest": self.prompt_digest,
            "schemaPath": self.schema_path,
            "schemaDigest": self.schema_digest,
            "timeoutSeconds": self.timeout_seconds,
            "maxOutputTokens": self.max_output_tokens,
            "maxInputTokensPerCall": self.max_input_tokens_per_call,
            "temperature": self.temperature,
            "topP": self.top_p,
            "retryPolicy": self.retry_policy,
            "expectedProviderCalls": self.expected_provider_calls,
            "apiKeyConfigured": bool(self.api_key),
        }

    @property
    def digest(self) -> str:
        return _canonical_digest(self.sanitized())

    @property
    def worst_case_cost_usd(self) -> float:
        """Worst case under the bound miss/output rates and 48 requests."""

        return self.expected_provider_calls * (
            self.max_input_tokens_per_call * 0.14 / 1_000_000
            + self.max_output_tokens * 0.28 / 1_000_000
        )


@dataclass(frozen=True, slots=True)
class ProviderCapture:
    """One provider response captured once for both post-processing arms."""

    payload: Any
    usage: Usage | None = None
    retry_count: int = 0


class ProviderAdapter(Protocol):
    """The only provider operation allowed by the frozen runner."""

    def capture(
        self,
        *,
        case_id: str,
        raw_text: str,
        prompt_version: str,
        provider_schema: str,
    ) -> ProviderCapture:
        """Make exactly one request and return its structured response."""


class ResponsesTransport(Protocol):
    """One-shot HTTP transport; implementations must not retry."""

    def post(
        self,
        *,
        url: str,
        api_key: str,
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        """Send one request and return a decoded JSON object."""


class UrllibChatCompletionsTransport:
    """Minimal no-retry transport for the OpenAI-compatible DeepSeek endpoint."""

    def post(
        self,
        *,
        url: str,
        api_key: str,
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        request = urllib.request.Request(
            url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except (
            OSError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as error:
            raise ProviderAdapterError(
                "provider request failed without retry"
            ) from error
        if not isinstance(decoded, dict):
            raise ProviderAdapterError("provider response is not a JSON object")
        return decoded


class DeepSeekProviderAdapter:
    """Concrete, digestable DeepSeek adapter for the guarded live entrypoint."""

    def __init__(
        self,
        configuration: DeepSeekRuntimeConfiguration,
        *,
        transport: ResponsesTransport | None = None,
        prompt_path: Path = DEFAULT_PROMPT_PATH,
        schema_path: Path = DEFAULT_SCHEMA_PATH,
    ) -> None:
        if configuration.retry_policy != EXPECTED_RETRY_POLICY:
            raise ProviderAdapterError("only the no-retry policy is permitted")
        if configuration.model != EXPECTED_MODEL:
            raise ProviderAdapterError("adapter model is not the frozen DeepSeek model")
        if configuration.provider_schema != EXPECTED_PROVIDER_SCHEMA:
            raise ProviderAdapterError(
                "adapter provider schema is not relation-evidence-envelope.v1"
            )
        self.configuration = configuration
        self._transport = transport or UrllibChatCompletionsTransport()
        self._prompt = prompt_path.read_text(encoding="utf-8")
        self._schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if not isinstance(self._schema, dict):
            raise ProviderAdapterError("provider schema artifact is not an object")
        if _file_digest(prompt_path) != configuration.prompt_digest:
            raise ProviderAdapterError(
                "prompt artifact digest does not match runtime configuration"
            )
        if _file_digest(schema_path) != configuration.schema_digest:
            raise ProviderAdapterError(
                "provider schema digest does not match runtime configuration"
            )

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        transport: ResponsesTransport | None = None,
    ) -> DeepSeekProviderAdapter:
        configuration = DeepSeekRuntimeConfiguration.from_environment(environment)
        return cls(configuration, transport=transport)

    @property
    def runtime_configuration_digest(self) -> str:
        return self.configuration.digest

    @property
    def adapter_class(self) -> str:
        return "DeepSeekProviderAdapter"

    @property
    def adapter_digest(self) -> str:
        """Digest of the concrete adapter module bound by the package."""

        return _file_digest(Path(__file__).resolve())

    def capture(
        self,
        *,
        case_id: str,
        raw_text: str,
        prompt_version: str,
        provider_schema: str,
    ) -> ProviderCapture:
        if prompt_version != self.configuration.prompt_version:
            raise ProviderAdapterError(
                "runner prompt version differs from frozen configuration"
            )
        if provider_schema != self.configuration.provider_schema:
            raise ProviderAdapterError(
                "runner provider schema differs from frozen configuration"
            )
        if not case_id or not raw_text:
            raise ProviderAdapterError("case id and source text are required")
        request_payload: dict[str, object] = {
            "model": self.configuration.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{self._prompt}\nExact JSON Schema to satisfy:\n"
                        f"{json.dumps(self._schema, ensure_ascii=False, sort_keys=True)}"
                    ),
                },
                {"role": "user", "content": raw_text},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.configuration.max_output_tokens,
            "temperature": self.configuration.temperature,
            "top_p": self.configuration.top_p,
            "thinking": {"type": "disabled"},
        }
        # Deliberately one transport call: this method has no retry path.
        response = self._transport.post(
            url=self.configuration.base_url,
            api_key=self.configuration.api_key,
            payload=request_payload,
            timeout_seconds=self.configuration.timeout_seconds,
        )
        content = _extract_message_content(response)
        try:
            payload = json.loads(content)
        except (TypeError, json.JSONDecodeError) as error:
            raise ProviderAdapterError(
                "provider returned non-JSON structured output"
            ) from error
        if not isinstance(payload, dict):
            raise ProviderAdapterError("provider structured output is not an object")
        usage = _usage(response.get("usage"))
        if usage["inputTokens"] > self.configuration.max_input_tokens_per_call:
            raise ProviderAdapterError(
                "provider input usage exceeded the frozen token bound"
            )
        if usage["outputTokens"] > self.configuration.max_output_tokens:
            raise ProviderAdapterError("provider output usage exceeded max_tokens")
        return ProviderCapture(payload=payload, usage=usage, retry_count=0)


def _extract_message_content(response: Mapping[str, object]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderAdapterError("provider response has no choice")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ProviderAdapterError("provider response has no message content")
    if choices[0].get("finish_reason") == "length":
        raise ProviderAdapterError(
            "provider output reached the frozen max_tokens bound"
        )
    content = message["content"]
    if not content:
        raise ProviderAdapterError("provider returned empty message content")
    return content


def _usage(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ProviderAdapterError("provider usage counters are missing")
    input_tokens = _nonnegative_int(value.get("prompt_tokens"), "prompt_tokens")
    output_tokens = _nonnegative_int(
        value.get("completion_tokens"), "completion_tokens"
    )
    hit = _nonnegative_int(
        value.get("prompt_cache_hit_tokens", value.get("cache_hit_tokens", 0)),
        "prompt_cache_hit_tokens",
    )
    miss_value = value.get("prompt_cache_miss_tokens", value.get("cache_miss_tokens"))
    miss = (
        input_tokens - hit
        if miss_value is None
        else _nonnegative_int(miss_value, "prompt_cache_miss_tokens")
    )
    if hit + miss != input_tokens:
        raise ProviderAdapterError("provider cache token counters do not reconcile")
    return {
        "inputTokens": input_tokens,
        "promptCacheHitTokens": hit,
        "promptCacheMissTokens": miss,
        "outputTokens": output_tokens,
    }


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProviderAdapterError(f"provider usage field {label} is invalid")
    return value


class CallableProviderAdapter:
    """Offline-only adapter used by tests; never accepted by live entrypoint."""

    def __init__(self, callback: Callable[..., ProviderCapture]) -> None:
        self._callback = callback

    def capture(
        self,
        *,
        case_id: str,
        raw_text: str,
        prompt_version: str,
        provider_schema: str,
    ) -> ProviderCapture:
        return self._callback(
            case_id=case_id,
            raw_text=raw_text,
            prompt_version=prompt_version,
            provider_schema=provider_schema,
        )
