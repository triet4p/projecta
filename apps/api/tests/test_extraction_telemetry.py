"""Telemetry redaction and schema tests."""

import logging

import pytest
from pydantic import ValidationError

from projecta_api.extraction.telemetry import ExtractionTelemetryEvent, emit_extraction_event


def test_telemetry_contains_counts_and_versions_only() -> None:
    event = ExtractionTelemetryEvent(
        event="extraction.completed",
        requestId="req-1",
        provider="deepseek",
        modelVersion="deepseek-v4-flash",
        promptVersion="m3.prompt.v2",
        schemaVersion="m3.v1",
        latencyMs=12,
        entityCount=1,
    )

    payload = event.model_dump(mode="json", by_alias=True)
    assert payload["entityCount"] == 1
    assert "rawText" not in payload
    assert "providerPayload" not in payload
    assert "apiKey" not in payload


def test_telemetry_rejects_raw_payload_fields() -> None:
    with pytest.raises(ValidationError):
        ExtractionTelemetryEvent(
            event="extraction.completed",
            requestId="req-1",
            provider="deepseek",
            modelVersion="v1",
            promptVersion="p1",
            schemaVersion="m3.v1",
            latencyMs=1,
            rawText="secret note",
        )


def test_emitter_uses_structured_extra_field(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        emit_extraction_event(
            logging.getLogger("projecta.test"),
            ExtractionTelemetryEvent(
                event="extraction.failed",
                requestId="req-1",
                provider="deepseek",
                modelVersion="v1",
                promptVersion="p1",
                schemaVersion="m3.v1",
                latencyMs=1,
                errorClass="timeout",
            ),
        )

    assert caplog.records[0].projecta_extraction["errorClass"] == "timeout"
