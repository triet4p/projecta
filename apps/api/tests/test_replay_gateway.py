"""Deterministic replay gateway tests."""

import os
from pathlib import Path

import pytest

from projecta_api.llm.gateway import GatewayRequest, NormalizedGatewayError
from projecta_api.llm.replay import ReplayGateway


def _fixture_path() -> Path:
    configured = os.environ.get("PROJECTA_REPLAY_FIXTURE")
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "evaluation" / "sprint-5" / "replay_outputs.v1.json"
        if candidate.is_file():
            return candidate
    raise RuntimeError("PROJECTA_REPLAY_FIXTURE is required when the replay fixture is not in the repository")


FIXTURE = _fixture_path()


def _request(case_id: str) -> GatewayRequest:
    return GatewayRequest(
        schemaVersion="m3.v1",
        modelId=f"replay:{case_id}",
        systemPrompt="system",
        userPrompt="user",
        responseSchema={"type": "object"},
    )


@pytest.mark.asyncio
async def test_replay_returns_versioned_typed_output() -> None:
    gateway = ReplayGateway.from_file(FIXTURE)

    result = await gateway.extract(_request("basic-requirement-001"))

    assert result.extraction.schema_version == "m3.v1"
    assert result.extraction.entities[0].type == "Requirement"


@pytest.mark.asyncio
async def test_replay_returns_explicit_abstention() -> None:
    gateway = ReplayGateway.from_file(FIXTURE)

    result = await gateway.extract(_request("empty-001"))

    assert result.extraction.entities == []
    assert result.extraction.abstention_reason == "no supported proposal"


@pytest.mark.asyncio
async def test_replay_fails_closed_for_unknown_case() -> None:
    gateway = ReplayGateway.from_file(FIXTURE)

    with pytest.raises(NormalizedGatewayError) as caught:
        await gateway.extract(_request("missing"))

    assert caught.value.error_class == "configuration_invalid"
