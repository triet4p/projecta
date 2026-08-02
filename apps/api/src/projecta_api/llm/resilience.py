"""Bounded retry policy for normalized provider gateway failures."""

import asyncio
from collections.abc import Awaitable, Callable

from projecta_api.llm.gateway import (
    GatewayRequest,
    GatewayResponse,
    LLMGateway,
    NormalizedGatewayError,
)


class ResilientGateway:
    """Retry only explicitly retryable errors within a fixed attempt budget."""

    def __init__(
        self,
        gateway: LLMGateway,
        *,
        max_retries: int = 2,
        base_delay_seconds: float = 0.05,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not 0 <= max_retries <= 3:
            raise ValueError("max_retries must be between 0 and 3")
        if not 0 <= base_delay_seconds <= 2:
            raise ValueError("base_delay_seconds must be between 0 and 2")
        self._gateway = gateway
        self._max_retries = max_retries
        self._base_delay_seconds = base_delay_seconds
        self._sleeper = sleeper

    async def extract(self, request: GatewayRequest) -> GatewayResponse:
        """Execute at most one initial attempt plus the configured retries."""
        for attempt in range(self._max_retries + 1):
            try:
                return await self._gateway.extract(request)
            except NormalizedGatewayError as error:
                if not error.retryable or attempt == self._max_retries:
                    raise
                await self._sleeper(self._base_delay_seconds * (2**attempt))
        raise AssertionError("retry loop must return or raise")
