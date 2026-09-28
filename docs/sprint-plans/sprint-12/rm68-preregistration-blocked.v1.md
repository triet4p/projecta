# S12-RM-68 External Validation Preparation — Deferred

Status: `DRAFT_BLOCKED_EXTERNAL_CUSTODY`

This is a strict blocked packet, not an issued preregistration, and is deferred
for development only. RM-65,
RM-66, and RM-67 are accepted, but the G6 source-of-truth packet records
`CUSTODY_NOT_ESTABLISHED`, an absent and reconstructible repository-visible
payload, no frozen candidate, and zero reviewer/manual records. No held-out
material was inspected or generated.

## Bound future inputs

The JSON packet binds the accepted RM-67 contract and schema, the RM-67
human-readable contract, metrics v1, the G6 protocol boundary, the blocked G6
packet, and the accepted human-first v2 design by SHA-256 digest. The future
issuance must add opaque digests for:

- an external custodian, custody receipt, non-reconstructibility attestation,
  dataset manifest, and payload;
- a frozen/evaluable candidate, configuration, and evaluator identity; and
- owner-approved blinded/counterbalanced protocol authority.

No dataset IDs, payloads, candidate IDs, configuration digests, custodian, or
human approval are invented in this packet; absent bindings remain `null`.

## Future protocol and gates

The prepared protocol preserves RM-67's three target roles (BrSE,
project-manager, semantic-reviewer), minimum three qualified reviewers, twelve
scenarios, thirty-six reviewer records, blinded independent annotation, and a
counterbalanced same-reviewer manual baseline. It references the RM-67
correction-burden thresholds, taxonomy, timing, denominators, missing-output/
rejection/abstention rules, and confidence-interval policy. Abort conditions
include custody, digest, hard-invariant, reviewer-independence, unsupported-
assertion, integrity, provider, held-out, and unauthorized-execution failures.

All issuance and execution locks remain false. No RM-68 action is permitted
until an owner explicitly reopens the gate with external custody and
frozen-candidate evidence. RM-68 remains unchecked; Phase F-RF is
`DEVELOPMENT_COMPLETE_EXTERNAL_VALIDATION_DEFERRED`. This packet does not claim
preregistration, human evidence, business-quality validation, threshold result,
provider execution, held-out access, selection, promotion, release, or
production authority.
