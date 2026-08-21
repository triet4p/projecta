# Task Summary: S12-RM-38 — Offline RM36 Reconciliation Diagnosis

**Status:** complete; offline diagnosis and remediation proposal prepared;
RM-39 owner review pending

RM-38 inspected the repository-visible v8 runner, RM-36/RM-37 sanitized
execution facts and the frozen first development case. No provider was called,
no runtime report was written and no frozen or issued lineage was changed.

## Finding

The first predicted-entities arm can fail because the two counters use
different domains. `v4.score_relations` records `unsupported`/`missing` only
for semantically exact relation pairs. RM-30's `_evidence_reasons` loop visits
every predicted relation. A non-exact or extra relation with invalid evidence
therefore adds a diagnostic reason without adding to `invalidEvidenceCount`.
The v8 guard raises before report persistence. A second adapter defect passes
`(start, end, type)` entity tuples to a classifier expecting `(start, end)`;
that can erase a more specific reason into
`materializer_detail_unavailable`.

The mock for `s12-a-4003` produces `exactMatch=0`,
`invalidEvidenceCount=0`, one `trigger_quote_missing` reason and the exact
historical exception. Existing tests missed this because they covered an exact
relation with missing evidence, where both counters were one.

## Artifacts and validation

- Diagnosis:
  `evaluation/sprint-12/optimization/s12-f-12-rm38-reconciliation-diagnosis.v1.json`
- Remediation proposal:
  `evaluation/sprint-12/optimization/s12-f-12-rm38-remediation-proposal.v1.json`
- Non-authoritative next state:
  `evaluation/sprint-12/current-state-next-rm38.v1.json`
- Non-authoritative G5 snapshot:
  `evaluation/sprint-12/optimization/g5-packet.v26.rm38-diagnosis-preparation.json`
- Reproducer:
  `scripts/s12_f12_rm38_reconciliation_diagnosis.py`
- Tests:
  `scripts/tests/test_sprint12_rm38_reconciliation_diagnosis.py`

Validation: `18 passed` across RM-38 diagnosis, v8 runtime diagnostics and
RM-36 custody tests. The only output was the known pytest cache permission
warning. RM-39 must decide whether the finite proposal may proceed to runtime
implementation.
