# S12-RM-20C summary

## Outcome

Completed the offline remediation for RM-21A identity and occurrence blockers.
V1, v2 and v3 packages remain immutable history; v4 is the superseding offline
package.

## Controls added

- Endpoint resolution now uses typed-span identity with one-to-one matching,
  independent of local candidate IDs. Duplicate, absent, drifted and wrong-type
  candidates have explicit reconciliation outcomes.
- Trigger occurrences are server-owned records containing half-open offsets and
  a quote digest. The scorer validates source bounds, quote digest, code-point
  width, selected sentence/clause containment, evidence containment and unique
  occurrence selection. Raw source text is not persisted.
- V4 preflight retains exact non-empty digest binding and validates the renamed
  local-ID oracle arm deterministically.

## Validation

- `5 passed` for RM-20C scorer and preflight tests.
- Full f12 v1–v4 regression: `26 passed`.
- Preflight: `OFFLINE_CONTRACTS_READY_ZERO_CALL_V4`.
- Ruff: pass.
- `git diff --check`: pass.
- Provider calls: `0`; held-out access: `false`.

## Governance boundary

RM-21B owner re-review is pending. No preregistration, execution freeze,
authorization or provider execution was issued.
