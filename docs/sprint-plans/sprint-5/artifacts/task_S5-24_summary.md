# Task Summary: S5-24 — Add safe extraction telemetry

**Sprint:** Sprint 5
**Task:** S5-24

## Summary of Work

Added a strict structured telemetry event containing correlation ID, provider,
model/prompt/schema versions, latency, usage counts, result counts, and safe
error class. Extra fields are forbidden, so raw notes, prompts, provider
payloads, credentials, arbitrary graph data, and secrets cannot enter the
event contract. Emission uses a structured logger extra field.

## Files Modified

- `apps/api/src/projecta_api/extraction/telemetry.py`
- `apps/api/tests/test_extraction_telemetry.py`

## Testing

- **Command:** `uv run pytest tests/test_extraction_telemetry.py -q`
- **Coverage:** allowlisted fields, raw-payload rejection, and structured emission.
