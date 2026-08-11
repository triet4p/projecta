# Task Summary: S10-07 — Define the PostgreSQL operational model

**Sprint:** Sprint 10 — Governed Connector Foundation and v0.5.0

**Task:** S10-07

## Summary of Work

Defined the PostgreSQL operational storage contract for installations, event
inbox, sync runs, single attempts, cursors, idempotency keys, dead letters,
audit events, and safe read projections. The document specifies project-scoped
keys/predicates, optimistic revisions, claim/replay/conflict semantics,
cross-store completion with Semantic Core/evidence, retention, migrations,
backup/restore, rollback, reconciliation, and the prohibition on raw
payloads/secrets/RDF operational state.

## Files Modified

* [docs/architecture/connector-operational-storage.md](F:/ai-ml/projecta/docs/architecture/connector-operational-storage.md) — PostgreSQL operational schema and lifecycle contract.
* [scripts/tests/test_sprint10_operational_storage_contract.py](F:/ai-ml/projecta/scripts/tests/test_sprint10_operational_storage_contract.py) — Deterministic storage-boundary guardrail tests.
* [docs/sprint-plans/sprint-10/artifacts/task_S10-07_summary.md](F:/ai-ml/projecta/docs/sprint-plans/sprint-10/artifacts/task_S10-07_summary.md) — Task traceability record.

## Testing

* **Test File:** [scripts/tests/test_sprint10_operational_storage_contract.py](F:/ai-ml/projecta/scripts/tests/test_sprint10_operational_storage_contract.py)
* **Status:** Passed.
* **Execution Command:** `uv run --no-project python -m unittest discover -s scripts/tests -p "test_sprint10_operational_storage_contract.py"`; `git diff --check`

## Additional Notes

This task defines the model only. PostgreSQL Compose, migrations, repositories,
atomic claim/cursor implementation, backup/restore tooling, and recovery tests
remain blocked until G1 approval and belong to later Sprint 10 tasks.
