# G5 optimization v35 — RM-50 offline diagnostics and parity fixtures

**Status:** preparation only; pending S12-RM-51 owner review  
**Date:** 2026-08-22

RM-49 approved the sequential offline path: Option A first, then Option B only
if A's stop criteria passed. RM-50 completed both stages without provider or
live-runner access.

Option A is recorded in
`evaluation/sprint-12/optimization/s12-f-12-rm50-offline-diagnostic-report.v1.json`
and its closed schema. It passes finite allowlists, exact reconciliation,
unknown fail-closed behavior, recursive/dynamic-key raw-data exclusion, and
the explicit J1/gold-entities evidence support/exact transition from
`not-applicable` in v6 to `0.0` in v9.

Option B is recorded in the versioned parity fixtures/report and schemas. It
covers 9 schema boundaries, 10 evidence boundaries, 7 scorer scenarios
(duplicate, order, tie, wrong predicate, reversed endpoint, extra, missing),
case/arm/stage/slice labels, and the v9 sanitized clusters: 5 schema-invalid,
20 invalid-evidence, 14 trigger-containment and 6 endpoint-containment. The
gold-relations control remains clean. No source text, trigger quote or provider
payload was reconstructed.

The package is
`evaluation/sprint-12/optimization/s12-f-12-rm50-offline-remediation.v1.json`;
the non-authoritative snapshot is
`evaluation/sprint-12/current-state-next-rm50.v1.json`.

RM-51 must independently review the package before any runtime remediation,
lineage preparation, authorization or provider work. All downstream gates stay
closed and the v6/v9 digests and v8 absence are preserved.
