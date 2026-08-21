# S12-RM-23B summary

## Outcome

RM-23B is complete with status
`OWNER_ISSUANCE_REVIEW_WITHHELD_ORACLE_SLICE_AND_GUARD_BLOCKERS`.
RM-22B successfully repaired exact-commit custody, aggregate denominators,
hard-gate wiring and pre-persist validation placement, but the v3 package is not
eligible for issuance or provider authorization.

## Verified

- Exact commit/blob custody passes for commit `99423f8`.
- Preflight returns `F12_RM22B_READY_ZERO_CALL_V3` with zero provider calls.
- Mock execution performs 144 calls, emits 96 relation branches and records the
  correct global denominators: 48 case-runs, 24 relations and 12 abstentions.
- The f12 regression set passes (`44 passed`); Ruff and diff-check pass.
- No real provider call, held-out access or final Stage A report occurred.

## Blocking findings

1. The zero-provider gold-relations control deterministically has six evidence
   failures across `s12-a-4007` and `s12-a-4015`, although the frozen threshold
   requires zero.
2. The runner emits relation-negative denominator `0` rather than `12`, mixes
   abstention cases with hard negatives, and applies non-applicable thresholds
   to every slice.
3. Decisive nested report structures remain open, and missing `jsonschema`
   activates a permissive fallback instead of failing closed.
4. The provider authorization guard does not require the experiment identity or
   explicit false locks for held-out, Stage B, selection and promotion.

## Governance boundary

Preregistration issuance, technical-freeze issuance, provider authorization,
Stage A execution, validation, held-out access, Stage B, selection and promotion
remain blocked. The next permitted task is offline RM-22C remediation followed
by a new independent RM-23C owner review.
