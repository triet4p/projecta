# S12-RM-50 — Offline diagnostic hardening and parity fixtures

**Status:** implemented offline; pending S12-RM-51 owner review  
**Date:** 2026-08-22

## Sequential gate

RM-49 authorized Option A followed conditionally by Option B. Option A passed
before Option B began:

- finite schema/evidence reason allowlists are closed;
- counts reconcile exactly and unknown reasons fail closed;
- recursive/dynamic-key raw-data aliases are rejected;
- J1/gold-entities support and exact transition is explicitly
  `not-applicable → 0.0` from v6 to v9.

Option B then passed deterministic parity fixtures with no provider or raw
source reconstruction:

- 9 schema boundaries and 10 evidence boundaries;
- trigger and endpoint containment classification;
- scorer cases for duplicate, order, tie, wrong predicate, reversed endpoint,
  extra and missing relations;
- 5 v9 schema-invalid and 20 v9 invalid-evidence clusters reproduced,
  including 14 trigger and 6 endpoint failures;
- gold-relations control remains clean.

The RM-51 tamper families are fail-closed before any pass or reconciliation
claim: v9 invalid-evidence count mutation, schema-finding removal, parity
cluster total/reason/case-run mutation, and direct diagnostic cluster/reason
map mutation. Totals and reproduction are derived from immutable source case
records and fixture case records; source v6/v9 digests and case/arm/stage
identity are checked.

The correction also rejects v6 invalid-evidence count mutation and any
caseId/runId/arm/stage identity change, plus semantic mutation of every
fixture field and cluster case (including cross-swap, duplicate, deletion and
addition).

## Artifacts and validation

The authoritative task package is
`evaluation/sprint-12/optimization/s12-f-12-rm50-offline-remediation.v1.json`.
Option A and B each have versioned modules, reports, schemas and tests. Tests
passed: Option A `27`, Option B `43` (including exhaustive mutation and
package digest custody), for `70` RM-50 tests. The combined safe regression
suite passed `88` tests. The known `.pytest_cache` permission warning is
environment-only.

The immutable v6/v9 digests remain bound and the v8 report remains absent.
RM-51 is the next gate. Runtime edits, lineage/authorization, provider calls,
reruns/retries, validation, held-out access, Stage B, selection and promotion
remain false.
