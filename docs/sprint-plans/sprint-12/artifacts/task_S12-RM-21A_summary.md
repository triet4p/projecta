# S12-RM-21A summary

## Outcome

Owner re-review is complete with status
`OWNER_REVIEW_WITHHELD_IDENTITY_AND_OCCURRENCE_BLOCKERS`.

RM-20B correctly closed the digest-binding gap and separated the named endpoint
counters. Two adversarial cases nevertheless show that the metrics are not yet
safe for a live preregistration:

- Semantically identical predicted entities with renamed local candidate IDs
  produce relation semantic TP `1` but missing-endpoint rate `1.0`.
- An eight-code-point trigger quote with a one-code-point occurrence span still
  receives evidence exact credit.

The full evidence and remediation criteria are recorded in
`evaluation/sprint-12/optimization/s12-f-12-offline-contracts-review.v3.json`.

## Validation repeated during review

- v1-v3 regression tests: `21 passed` (one pytest cache warning).
- Preflight: `OFFLINE_CONTRACTS_READY_ZERO_CALL_V3`.
- Ruff: pass.
- `git diff --check`: pass before adding the review artifacts.
- Provider calls: `0`; held-out access: `false`.

## Governance boundary

Only offline RM-20C remediation is permitted. Preregistration preparation,
execution freeze, provider authorization, validation, Stage B, selection and
promotion remain closed pending a separate owner re-review.
