"""Bounded retry and fail-closed resilience tests."""

import pytest

from projecta_api.llm.gateway import GatewayRequest, GatewayResponse, NormalizedGatewayError
from projecta_api.llm.resilience import ResilientGateway


def _request() -> GatewayRequest:
    return GatewayRequest(schemaVersion="m3.v1", modelId="replay:x", systemPrompt="s", userPrompt="u", responseSchema={})


class FailingGateway:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def extract(self, request: GatewayRequest) -> GatewayResponse:
        self.calls += 1
        if self.calls <= self.failures:
            raise NormalizedGatewayError("rate_limit", "retryable", retryable=True)
        return GatewayResponse.model_construct(extraction=None, usage=None)


@pytest.mark.asyncio
async def test_retries_are_bounded_and_backoff_is_injected() -> None:
    gateway = FailingGateway(2)
    delays: list[float] = []

    async def sleeper(delay: float) -> None:
        delays.append(delay)

    result = await ResilientGateway(gateway, max_retries=2, sleeper=sleeper).extract(_request())

    assert result.extraction is None
    assert gateway.calls == 3
    assert delays == [0.05, 0.1]


@pytest.mark.asyncio
async def test_non_retryable_error_is_not_retried() -> None:
    gateway = FailingGateway(1)

    async def extract(_: GatewayRequest) -> GatewayResponse:
        gateway.calls += 1
        raise NormalizedGatewayError("schema_invalid", "invalid", retryable=False)

    gateway.extract = extract  # type: ignore[method-assign]
    with pytest.raises(NormalizedGatewayError):
        await ResilientGateway(gateway, max_retries=3).extract(_request())

    assert gateway.calls == 1
