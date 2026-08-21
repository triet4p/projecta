# S12-RM-22A summary

## Outcome

RM-22A offline remediation is complete with status
`F12_RM22A_READY_ZERO_CALL_V2`. RM-22 v1 remains historical evidence and was
not modified. The superseding v2 issuance draft, execution package and
technical freeze are prepared for RM-23A owner review only.

## Remediation completed

- Added a concrete no-retry Stage 2-aware adapter requiring the explicit arm
  and canonical candidate table; Stage 1 rejects a candidate table.
- Implemented the guarded runner: exact `144` calls (`48` Stage 1 predicted,
  `48` Stage 2 predicted, `48` Stage 2 gold), `96` relation branches, no retry,
  no overwrite, single final persistence and sanitized report fields.
- Expanded the report schema for custody, configuration, accounting,
  usage/pricing, failure classes, per-case arms, slices and final decision.
- Recomputed all denominators from the frozen atomic corpus and reconciled the
  registered 16 cases, 8 positive-relation cases, 4 abstention cases, 24
  relation instances, 12 abstention instances and named journey/language
  slices.
- Bound the RM-23 review, runner, adapter, preflight, report schema, mock E2E
  test, preregistration draft and all source/corpus artifacts by digest.

## Validation

- Mock authorized execution: `4 passed`, including exact `144` calls and one
  persisted output.
- RM-22A preflight: `F12_RM22A_READY_ZERO_CALL_V2`.
- Relevant regression set: `12 passed`.
- Ruff: pass; `git diff --check`: pass.
- Provider calls: `0`; held-out access: `false`; Stage A output: absent.

## Governance boundary

RM-23A owner issuance re-review is the next gate. No preregistration issuance,
technical freeze issuance, provider authorization or provider execution is
granted by RM-22A.
