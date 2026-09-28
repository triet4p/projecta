# Sprint 12 Human Correction-Burden Contract v1

Status: `OWNER_DELEGATED_ACCEPTED_FOR_RM68_PREREGISTRATION_ONLY`

This is a closed-world contract decision, not a study result. It reconciles
the approved G1 threshold table, G6 reviewer protocol, the accepted v2
human-first framework, and the existing metrics contract. The v1 framework is
retained as an immutable proposal/source record; v2 is the accepted design
bound by this contract. The owner-delegated decision is
accepted only as input to RM-68 preregistration. External custody, a frozen
candidate, blinded execution and human evidence remain prerequisites.

## Decision and thresholds

- At least 70% of eligible reviewed items must be accepted without semantic
  correction (`unchanged`, including deterministically mapped formatting-only
  records with zero semantic/evidence dimensions); at least 85% must be accepted unchanged or with a
  `minor` correction.
- Projecta median review time must be at least 30% below the counterbalanced,
  same-reviewer manual-entry baseline. Absolute guardrails are median ≤45s and
  p90 ≤90s. Metrics v1's P95 remains a required descriptive slice report.
- Mean semantic edits must be ≤2 per reviewed item. The item denominator is the
  primary, stricter named denominator; note-level aggregation is secondary.
- Unsupported finalized assertions must be zero. Reviewer agreement is ≥0.80
  on applicable independently double-reviewed records; unavailable agreement
  is blocked evidence, not a passing zero.

## Taxonomy and accounting

`unchanged` means no semantic or evidence correction. `minor` is limited to
span/label correction. `major` includes type, predicate, endpoint or evidence
correction. Major wins over minor; minor wins over unchanged. Unknown dimensions
fail the contract. Legacy G1 classes map formatting-only to unchanged because it
has no semantic/evidence dimension, while minor-semantic maps to minor and
major-semantic to major. Span/label edits remain minor and therefore do not enter
the 70% no-semantic-correction numerator; rejection and missing output are
dispositions, not correction successes.

Rejected, abstained and missing-output records remain in acceptance denominators.
Malformed, duplicate, stale, tampered or digest-unbound records block rather
than disappear. Disagreements are measured before adjudication; adjudication
records a separate outcome and cannot overwrite independent decisions.

Timing starts when verified evidence is loaded and an explicit action is
available, and stops on durable receipt acknowledgement. Only explicit pause,
hidden/disabled review state, navigation away or ≥60s idle pauses the timer;
all pause segments must be bounded and non-overlapping. The manual baseline uses
the same policy, matched material, same reviewers and counterbalanced order.

## Required future study shape

The minimum is three qualified target roles (BrSE, project-manager and
semantic-reviewer), 12 scenarios and 36 reviewer records, with the eight G0
journeys represented. At least two scenarios each cover Vietnamese, English,
Japanese and mixed language; at least two cover ambiguity and at least two cover
threat/isolation slices including prompt injection, fabricated links and
cross-project boundaries. This contract does not create or inspect those
records.

Confidence intervals follow metrics v1: preregistered 95% bootstrap or exact
methods by metric, with cases as atomic resampling units, episodes for scenario
metrics and matched reviewer records/case pairs for reviewer metrics. F1 is
diagnostic only and cannot substitute for correction-burden evidence.

No observed human results, held-out inspection, provider calls, ontology or
runtime changes, production enablement, RM-68 preregistration, or study
execution is claimed.
