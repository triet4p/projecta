# S12-RM-20D summary

## Outcome

Completed the offline remediation for RM-21B endpoint reuse and source-proof
blockers. V1 through v4 remain immutable history; v5 is the superseding offline
package.

## Controls added

- Distinct gold entities are mapped to predicted typed spans once. The resulting
  mapping is reused for every relation endpoint slot, so shared sources,
  shared targets and cycles do not consume a valid candidate.
- The runtime-only materializer derives `quoteDigest` from
  `source[start:end]`. The scorer verifies source length/digest, exact source
  slice content, code-point width, sentence/clause boundaries and occurrence
  containment. Reports persist only sanitized metadata.
- The v5 oracle graph includes `g1->g2` and `g1->g3`; both relation slots reuse
  the same source mapping and resolve all four endpoint slots.

## Validation

- `5 passed` for RM-20D scorer and preflight tests.
- Full f12 v1–v5 regression: `31 passed`.
- Preflight: `OFFLINE_CONTRACTS_READY_ZERO_CALL_V5`.
- Ruff: pass.
- `git diff --check`: pass.
- Provider calls: `0`; held-out access: `false`.

## Governance boundary

RM-21C owner re-review is pending. No preregistration, execution freeze,
authorization or provider execution was issued.
