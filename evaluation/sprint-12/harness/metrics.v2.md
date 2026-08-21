# Sprint 12 Metric Contract v2

**Status:** `G3.1_A_MEASUREMENT_CONTRACT_FROZEN_PENDING_INSTRUMENTATION`

Metric contract v2 supersedes the scoring definitions for future Sprint 12
runs. `metric-contract.v1.json`, the v2 evaluator, and all f07/f08 reports are
historical evidence and remain unchanged.

## Relation metrics

`relationSemanticF1` uses only the semantic identity:

```text
(predicate, canonical source endpoint, canonical target endpoint)
```

The canonical endpoint is `(startOffset, endOffset, releasedEntityType)`.
Relation evidence offsets are excluded from this identity, so a semantically
correct relation with a wrong boundary is not scored as a semantic relation
false negative.

Evidence is reported independently for semantically matched relation pairs:

- `relationEvidenceSupport` is the fraction whose evidence passes source and
  code-point integrity plus the versioned support policy for the endpoints and
  predicate trigger.
- `relationEvidenceExact` is the fraction whose half-open offsets equal one of
  the adjudicated valid gold spans for that same semantic relation.

Both evidence metrics use semantic relation true positives as their
denominator. If that denominator is zero, the metric is `not-applicable`; it
does not turn semantic relation quality into zero.

The historical `relations.f1` exact predicate-endpoint-span score remains
reportable for continuity only. It is not the semantic relation quality gate.

## Reporting and custody

Every case and slice must publish its denominators and all three relation
metrics. Pooled-only summaries and inferred denominators are forbidden.
Provider execution remains blocked until G3.1-A instrumentation and fixtures
pass.
