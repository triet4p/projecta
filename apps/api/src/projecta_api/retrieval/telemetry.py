"""Redacted M4 telemetry fields."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalTelemetry:
    contract_version: str
    query_id: str
    elapsed_ms: int
    result_count: int
    citation_count: int
    status_mix: tuple[str, ...]
    abstained: bool
    error_class: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {"contractVersion": self.contract_version, "queryId": self.query_id,
                "elapsedMs": self.elapsed_ms, "resultCount": self.result_count,
                "citationCount": self.citation_count, "statusMix": list(self.status_mix),
                "abstained": self.abstained, "errorClass": self.error_class}
