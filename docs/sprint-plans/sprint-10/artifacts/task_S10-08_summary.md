# Task Summary: S10-08 — Define the raw-evidence storage contract

**Sprint:** Sprint 10 — Governed Connector Foundation and v0.5.0

**Task:** S10-08

## Summary of Work

Defined the provider-neutral evidence-store port and raw-evidence contract for
immutable/content-addressed writes, bounded streaming reads, media/size
allowlists, digest verification, project isolation, retention/deletion,
sanitized errors, restart/backup/restore, and replay safety. The contract keeps
raw payloads out of browser responses, PostgreSQL operational rows, RDF, logs,
and telemetry while preserving future S3-compatible adapter compatibility.

## Files Modified

* [docs/architecture/connector-evidence-storage.md](F:/ai-ml/projecta/docs/architecture/connector-evidence-storage.md) — Evidence object-store port and safety contract.
* [scripts/tests/test_sprint10_evidence_contract.py](F:/ai-ml/projecta/scripts/tests/test_sprint10_evidence_contract.py) — Deterministic evidence-boundary guardrail tests.
* [docs/sprint-plans/sprint-10/artifacts/task_S10-08_summary.md](F:/ai-ml/projecta/docs/sprint-plans/sprint-10/artifacts/task_S10-08_summary.md) — Task traceability record.

## Testing

* **Test File:** [scripts/tests/test_sprint10_evidence_contract.py](F:/ai-ml/projecta/scripts/tests/test_sprint10_evidence_contract.py)
* **Status:** Passed.
* **Execution Command:** `uv run --no-project python -m unittest discover -s scripts/tests -p "test_sprint10_evidence_contract.py"`; `git diff --check`

## Additional Notes

The local/Compose adapter, PostgreSQL metadata, object-store volume, backup,
restore, and retention worker are implementation work after G1. Proposed limits
and deletion rules remain human-review inputs.
