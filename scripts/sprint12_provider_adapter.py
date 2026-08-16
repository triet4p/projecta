"""Provider boundary for the S12-f-10 shared-response runner.

The runner owns pairing, schema validation, scoring and report custody.  A
provider adapter owns only one operation: returning one structured response
and its provider-neutral usage counters for one case/run.  Keeping this
boundary injectable makes the complete execution package testable offline
without smuggling a provider SDK, credentials, retries or raw payloads into
the evaluation harness.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

Usage = Mapping[str, int | None]


@dataclass(frozen=True, slots=True)
class ProviderCapture:
    """One provider response captured once for both post-processing arms."""

    payload: Any
    usage: Usage | None = None


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


class CallableProviderAdapter:
    """Adapter used by offline tests and an explicitly bound gateway."""

    def __init__(
        self,
        callback: Callable[..., ProviderCapture],
    ) -> None:
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
