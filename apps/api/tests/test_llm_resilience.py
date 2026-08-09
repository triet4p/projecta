"""Bounded retry and fail-closed resilience tests."""

import logging

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

    result = await ResilientGateway(
        gateway, mode="operator-recovery", max_retries=2, sleeper=sleeper
    ).extract(_request())

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
        await ResilientGateway(gateway, mode="operator-recovery", max_retries=3).extract(_request())

    assert gateway.calls == 1


@pytest.mark.asyncio
async def test_interactive_mode_is_single_attempt_even_for_retryable_errors() -> None:
    gateway = FailingGateway(10)

    with pytest.raises(NormalizedGatewayError):
        await ResilientGateway(gateway, mode="interactive-single-attempt", max_retries=3).extract(_request())

    assert gateway.calls == 1


@pytest.mark.asyncio
async def test_schema_invalid_is_not_retried_by_operator_mode() -> None:
    gateway = FailingGateway(1)

    async def extract(_: GatewayRequest) -> GatewayResponse:
        gateway.calls += 1
        raise NormalizedGatewayError("schema_invalid", "invalid", retryable=True)

    gateway.extract = extract  # type: ignore[method-assign]
    with pytest.raises(NormalizedGatewayError):
        await ResilientGateway(gateway, mode="operator-recovery", max_retries=3).extract(_request())

    assert gateway.calls == 1


@pytest.mark.asyncio
async def test_attempt_events_are_correlated_and_payload_free() -> None:
    gateway = FailingGateway(1)
    events: list[dict[str, object]] = []

    class EventHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            events.append(record.projecta_provider_attempt)  # type: ignore[attr-defined]

    logger = logging.getLogger("test-provider-attempt")
    handler = EventHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        request = _request().model_copy(
            update={
                "request_id": "req-1",
                "operation_id": "op-1",
                "profile_revision": "4",
            }
        )
        await ResilientGateway(
            gateway, mode="operator-recovery", max_retries=1, provider="openai-response", logger=logger
        ).extract(request)
    finally:
        logger.removeHandler(handler)

    assert [event["event"] for event in events] == [
        "provider.attempt.started",
        "provider.attempt.completed",
        "provider.attempt.started",
        "provider.attempt.completed",
    ]
    assert {event["requestId"] for event in events} == {"req-1"}
    assert {event["operationId"] for event in events} == {"op-1"}
    assert {event["attempt"] for event in events} == {1, 2}
    assert all("prompt" not in event and "payload" not in event for event in events)
