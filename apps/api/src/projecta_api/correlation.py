"""Validated request/operation correlation identities for the API boundary."""

from dataclasses import dataclass
from re import fullmatch
from typing import TypeGuard
from uuid import uuid4

_CORRELATION_ID = r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}"


def is_safe_correlation_id(value: str | None) -> TypeGuard[str]:
    """Return whether a correlation ID is bounded and safe to emit."""

    return value is not None and fullmatch(_CORRELATION_ID, value) is not None


def new_request_id() -> str:
    """Create a server-owned request correlation identity."""

    return f"req-{uuid4().hex}"


def new_operation_id() -> str:
    """Create a server-owned operation identity."""

    return f"op-{uuid4().hex}"


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """The correlation pair propagated across every downstream boundary."""

    request_id: str
    operation_id: str

    def headers(self) -> dict[str, str]:
        """Return only the two approved correlation headers."""

        return {"X-Request-Id": self.request_id, "X-Operation-Id": self.operation_id}


def resolve_correlation(request_hint: str | None, operation_hint: str | None) -> CorrelationContext:
    """Accept safe hints or replace malformed/missing values at the trusted API boundary."""

    request_id = request_hint if is_safe_correlation_id(request_hint) else new_request_id()
    operation_id = operation_hint if is_safe_correlation_id(operation_hint) else new_operation_id()
    return CorrelationContext(request_id=request_id, operation_id=operation_id)
