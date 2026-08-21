# S12-RM-23A summary

## Outcome

RM-23A is complete with status
`OWNER_ISSUANCE_REVIEW_WITHHELD_MEASUREMENT_AND_LINEAGE_BLOCKERS`.
RM-22A materially fixed the earlier non-executable runner, candidate-table input,
frozen-gold denominator preflight and empty report-schema problems, but the v2
lineage is not safe to issue or authorize.

## Verified

- The zero-call preflight returns `F12_RM22A_READY_ZERO_CALL_V2`.
- The mocked happy path performs exactly 144 calls and writes once.
- Frozen gold yields 16 cases, 24 relation instances and 12 abstention instances
  over three runs.
- The f12 regression set passes (`41 passed`); Ruff and diff-check pass.
- No provider call, held-out access or Stage A report occurred.

## Blocking findings

1. The package requires exact-commit authorization, but the runner rejects a
   non-null freeze commit and does not validate an authorization commit.
2. The runner triple-counts aggregate relation/abstention denominators and does
   not emit the approved aggregate semantic/evidence metrics.
3. Two approved hard gates and all numeric thresholds are missing or unenforced;
   `invalidEvidence` is hard-coded to zero.
4. Required negative, journey and language slices are absent; the report schema
   remains permissive and is not applied before immutable persistence.

## Governance boundary

Preregistration issuance, technical-freeze issuance, provider authorization,
Stage A execution, validation, held-out access, Stage B, selection and promotion
remain blocked. The next permitted task is offline RM-22B remediation followed
by a new independent RM-23B owner review.
