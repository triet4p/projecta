#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Stage-2-aware concrete adapter for the superseding f12 package."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from sprint12_f12_provider_adapter import (
    PROMPT_VERSION,
    F12ProviderAdapter,
    ProviderAdapterError,
    ProviderCapture,
    _extract_message_content,
    _usage,
)


class F12ProviderAdapterV2(F12ProviderAdapter):
    """One-shot provider adapter with an explicit immutable Stage-2 table."""

    def capture_stage(
        self,
        *,
        stage: str,
        case_id: str,
        run_id: str,
        raw_text: str,
        arm: str,
        candidate_table: Sequence[Mapping[str, object]] | None = None,
    ) -> ProviderCapture:
        if stage not in {"stage1", "stage2"}:
            raise ProviderAdapterError("unknown f12 stage")
        if (
            not case_id
            or not run_id
            or not raw_text
            or self.configuration.prompt_version != PROMPT_VERSION
        ):
            raise ProviderAdapterError("invalid f12 request identity")
        if stage == "stage1":
            if arm != "predicted-entities" or candidate_table is not None:
                raise ProviderAdapterError("stage 1 must not receive a candidate table")
        elif (
            arm not in {"predicted-entities", "gold-entities"}
            or candidate_table is None
        ):
            raise ProviderAdapterError(
                "stage 2 requires an explicit candidate table and arm"
            )
        if candidate_table is not None:
            for index, candidate in enumerate(candidate_table):
                if set(candidate) != {
                    "candidateId",
                    "type",
                    "startOffset",
                    "endOffset",
                    "confidence",
                }:
                    raise ProviderAdapterError(
                        f"candidate table item {index} is not canonical"
                    )
        schema = self._schemas[stage]
        user_context = {
            "sourceText": raw_text,
            "stage": stage,
            "arm": arm,
            "candidateTable": list(candidate_table)
            if candidate_table is not None
            else None,
        }
        payload: dict[str, object] = {
            "model": self.configuration.model,
            "messages": [
                {
                    "role": "system",
                    "content": f"{self._prompt}\nExact JSON Schema:\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        user_context, ensure_ascii=False, sort_keys=True
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.configuration.max_output_tokens,
            "temperature": self.configuration.temperature,
            "top_p": self.configuration.top_p,
            "thinking": {"type": "disabled"},
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
            raise ProviderAdapterError(
                "provider returned non-JSON stage output"
            ) from error
        if not isinstance(decoded, dict):
            raise ProviderAdapterError("provider stage output is not an object")
        usage = _usage(response.get("usage"))
        if (
            usage["inputTokens"] > self.configuration.max_input_tokens_per_call
            or usage["outputTokens"] > self.configuration.max_output_tokens
        ):
            raise ProviderAdapterError(
                "provider usage exceeded the frozen token bounds"
            )
        return ProviderCapture(payload=decoded, usage=usage, retry_count=0)
