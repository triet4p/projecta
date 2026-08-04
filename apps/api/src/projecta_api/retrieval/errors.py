"""Finite M4 retrieval error taxonomy."""

from enum import StrEnum


class RetrievalErrorCode(StrEnum):
    UNKNOWN_INTENT = "unknown_intent"
    UNSUPPORTED_FILTER = "unsupported_filter"
    INVALID_ENTITY = "invalid_entity"
    AMBIGUOUS_MATCH = "ambiguous_match"
    NO_EVIDENCE = "no_evidence"
    STALE_PROJECTION = "stale_projection"
    RULE_FAILURE = "rule_failure"
    MALFORMED_PROVIDER_OUTPUT = "malformed_provider_output"
    TIMEOUT = "timeout"
    UNAVAILABLE_DEPENDENCY = "unavailable_dependency"
    CROSS_PROJECT_ACCESS = "cross_project_access"


class RetrievalError(Exception):
    """Sanitized, typed failure that never contains source payloads."""

    def __init__(self, code: RetrievalErrorCode, detail: str = "retrieval request failed") -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)
