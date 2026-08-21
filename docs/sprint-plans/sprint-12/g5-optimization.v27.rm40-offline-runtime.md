# Sprint 12 G5 — RM-40 Offline Runtime Remediation

**Status:** `G5_F12_RM40_OFFLINE_RUNTIME_REMEDIATION_IMPLEMENTED_PENDING_RM41_OWNER_REVIEW`

RM-39 approved implementation of the RM-38 fix only. RM-40 adds the new
versioned module `scripts/s12_f12_rm40_offline_runtime.py`; the issued v8
runner, v8 schema/authentication, RM-36 execution fact and historical v6
report remain untouched.

The implementation uses the same greedy exact semantic-pair domain as
`score_relations`. Evidence reasons are computed only for those pairs, so
wrong, extra and missing semantic relations cannot inflate the invalid-evidence
denominator. Entity spans are explicitly projected from `(start,end,type)` to
`(start,end)`, malformed detail maps to the registered
`materializer_detail_unavailable` reason, and reconciliation mismatches fail
closed.

The package is
`evaluation/sprint-12/optimization/s12-f-12-rm40-offline-runtime-package.v1.json`.
Focused mocks cover exact-invalid, non-exact-invalid, extra-invalid,
wrong/missing semantics, span projection, malformed detail, all-valid output,
mismatch refusal, raw-data exclusion and prospective 144/96 one-persist,
no-retry/no-overwrite custody. The path performs zero provider calls.

RM-41 is the next owner gate. No superseding lineage, issuance, provider
execution, validation, held-out access, Stage B, selection or promotion is
authorized.
