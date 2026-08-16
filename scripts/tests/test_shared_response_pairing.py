"""Offline tests for tool-only shared-response pairing."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared_response_pairing import (
    CapturedProviderResponse,
    branch_captured_response,
)


def test_control_and_candidate_branch_the_same_captured_response() -> None:
    payload = {"entities": [{"candidateId": "e-1"}], "relations": []}
    captured = CapturedProviderResponse.capture("case-1", payload)
    result = branch_captured_response(
        captured,
        {
            "control": lambda value: {"tool": "legacy", "payload": value},
            "candidate": lambda value: {"tool": "server-owned", "payload": value},
        },
    )

    assert result["providerCallCount"] == 1
    assert result["branchCount"] == 2
    assert result["branchInputDigests"]["control"] == captured.digest
    assert result["branchInputDigests"]["candidate"] == captured.digest
    assert result["outputs"]["control"]["payload"] == payload
    assert result["outputs"]["candidate"]["payload"] == payload


def test_branch_mutation_cannot_overwrite_captured_payload() -> None:
    payload = {"relations": [{"predicate": "supports"}]}
    captured = CapturedProviderResponse.capture("case-2", payload)

    def mutate(value: dict) -> dict:
        value["relations"].clear()
        return value

    branch_captured_response(captured, {"candidate": mutate})

    assert captured.payload == payload
    assert captured.provider_call_count == 1
