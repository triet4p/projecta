"""Deterministic replay gateway backed by versioned JSON fixtures."""

import json
from pathlib import Path
from typing import cast

from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.llm.gateway import (
    GatewayRequest,
    GatewayResponse,
    LLMGateway,
    NormalizedGatewayError,
)


class ReplayGateway(LLMGateway):
    """Return a pre-recorded typed result selected by ``replay:<case-id>``."""

    def __init__(self, responses: dict[str, ExtractionResponse]) -> None:
        self._responses = responses

    @classmethod
    def from_file(cls, path: Path) -> "ReplayGateway":
        """Load and validate a versioned replay fixture without network access."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            records = raw["responses"]
            if not isinstance(records, dict):
                raise TypeError("responses must be an object")
            responses = {
                str(case_id): ExtractionResponse.model_validate(payload)
                for case_id, payload in cast(dict[object, object], records).items()
            }
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise NormalizedGatewayError(
                "configuration_invalid", "replay fixture is invalid", retryable=False
            ) from error
        return cls(responses)

    async def extract(self, request: GatewayRequest) -> GatewayResponse:
        """Return the fixture selected by a replay model ID."""
        if not request.model_id.startswith("replay:"):
            raise NormalizedGatewayError(
                "configuration_invalid", "replay request is missing a fixture case", retryable=False
            )
        case_id = request.model_id.removeprefix("replay:")
        result = self._responses.get(case_id)
        if result is None:
            raise NormalizedGatewayError(
                "configuration_invalid", "replay fixture case is unavailable", retryable=False
            )
        return GatewayResponse(extraction=result, usage=result.usage)
