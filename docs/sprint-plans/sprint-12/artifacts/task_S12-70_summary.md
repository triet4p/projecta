# S12-70 — Prepare the draft G4 packet

Prepared the G4 packet, metric contract, finite error taxonomy and JSON/Markdown
baseline report. The packet binds dataset and manifest digests and records the
runtime-backed failure boundary without claiming baseline quality.

## Testing

`uv run --project apps/api --env-file .env python scripts/sprint12_evaluator.py`
generated the report with 160 accounted cases, 55 missing outputs and status
`RUNTIME_BACKED_WITH_FAILURES`.
