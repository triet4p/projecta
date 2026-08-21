# Sprint 12 G5 — RM-38 Offline Diagnosis Preparation

**Status:** `G5_F12_RM38_OFFLINE_DIAGNOSIS_COMPLETE_PENDING_RM39_OWNER_REVIEW`

RM-38 reproduced the RM-36 first-case predicted-entities reconciliation
exception with deterministic repository-local mocks. The primary defect is a
count-domain mismatch: `score_relations` counts invalid evidence only for
semantically exact pairs, while `_evidence_reasons` diagnoses every predicted
relation, including non-exact and extra relations. A non-exact invalid relation
therefore contributes zero to the arm materializer count and one finite reason,
raising the reconciliation guard. The endpoint-span adapter also passes
three-tuples to a two-tuple classifier and can degrade an otherwise specific
reason to `materializer_detail_unavailable`.

The diagnosis and finite remediation proposal are:

- `evaluation/sprint-12/optimization/s12-f-12-rm38-reconciliation-diagnosis.v1.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm38-remediation-proposal.v1.json`

The reproducer and focused tests use zero provider calls and retain no raw
source, provider payload or validation detail. They preserve the RM-36 fact of
three calls before failure, the absent v8 report, the spent authorization and
the immutable v6 digest. The hidden provider payload is unavailable; the
deterministic reproduction establishes the code-path defect but does not claim
that the hidden response had the same semantic mismatch.

RM-39 is the next owner gate. Runtime implementation, provider execution,
retry/rerun, superseding-lineage preparation, issuance, validation, held-out,
Stage B, selection and promotion remain closed.
