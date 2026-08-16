"""Provider-response capture and deterministic branch isolation for S12.

The module is intentionally provider-agnostic.  A future runner may capture
one provider response, then use :func:`branch_captured_response` for control
and candidate post-processing.  It never performs a provider call itself.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


def _jsonable(value: Any) -> Any:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", by_alias=True)
    return value


def response_digest(value: Any) -> str:
    payload = json.dumps(
        _jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CapturedProviderResponse:
    """Immutable metadata for exactly one captured provider response."""

    case_id: str
    payload: Any
    digest: str
    provider_call_count: int = 1

    @classmethod
    def capture(cls, case_id: str, payload: T) -> CapturedProviderResponse:
        if not case_id:
            raise ValueError("case_id must not be empty")
        return cls(
            case_id=case_id,
            payload=copy.deepcopy(payload),
            digest=response_digest(payload),
        )


def branch_captured_response(
    captured: CapturedProviderResponse,
    branches: Mapping[str, Callable[[T], Any]],
) -> dict[str, Any]:
    """Apply independent post-processing branches to one response snapshot.

    Each branch receives a deep copy.  The returned record exposes the source
    digest and provider-call count so a runner can fail closed if it attempts
    to compare different provider responses.
    """

    if not branches:
        raise ValueError("at least one post-processing branch is required")
    outputs: dict[str, Any] = {}
    input_digests: dict[str, str] = {}
    for name, processor in branches.items():
        if not name:
            raise ValueError("branch names must not be empty")
        branch_input = copy.deepcopy(captured.payload)
        input_digests[name] = response_digest(branch_input)
        outputs[name] = processor(branch_input)
    if any(digest != captured.digest for digest in input_digests.values()):
        raise RuntimeError("branch input digest changed before post-processing")
    return {
        "caseId": captured.case_id,
        "providerCallCount": captured.provider_call_count,
        "branchCount": len(outputs),
        "sourceResponseDigest": captured.digest,
        "branchInputDigests": input_digests,
        "outputs": outputs,
    }
