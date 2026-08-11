# Task Summary: S10-01 — Freeze the v0.4.0 compatibility baseline

**Sprint:** Sprint 10 — Governed Connector Foundation and v0.5.0

**Task:** S10-01

## Summary of Work

Recorded the released v0.4.0 public compatibility baseline before connector
implementation. The baseline covers the exact annotated tag target, component
versions, complete public Application API route inventory, projection and
trust-boundary invariants, Compose profiles and operational-storage boundary,
release validation totals, and tag-triggered workflow jobs. It explicitly
separates released evidence from future Sprint 10 work and keeps S10-10/G1
approval pending.

## Files Modified

* [docs/architecture/v0.4.0-compatibility-baseline.md](F:/ai-ml/projecta/docs/architecture/v0.4.0-compatibility-baseline.md) — Frozen v0.4.0 route, projection, version, Compose, validation, and release baseline.
* [docs/sprint-plans/sprint-10/artifacts/task_S10-01_summary.md](F:/ai-ml/projecta/docs/sprint-plans/sprint-10/artifacts/task_S10-01_summary.md) — Task traceability and validation record.

## Testing

* **Test File:** Not applicable; this is a documentation and release-evidence task.
* **Status:** Passed.
* **Execution Command:** `git rev-parse v0.4.0^{}`; `git show -s --format=... v0.4.0`; OpenAPI route extraction; `uv run python scripts/check_release_contract.py --tag v0.4.0`; `git diff --check`

## Additional Notes

The current v0.4.0 baseline uses the existing local operational database volume
and path. PostgreSQL connector state, raw evidence storage, connector routes,
and the runtime-placement decision remain Sprint 10 design work and are blocked
by G1. No production ontology vocabulary is changed by S10-01.
