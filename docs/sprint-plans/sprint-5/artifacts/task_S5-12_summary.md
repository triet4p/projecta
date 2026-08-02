# Task Summary: S5-12 — Define evaluation metrics and release thresholds

**Sprint:** Sprint 5
**Task:** S5-12

## Summary of Work

Defined schema validity, entity/relation F1, exact Unicode span, link accuracy,
abstention, calibration, latency, and cost metrics. Added slice-level
reporting, safety/rollback hard gates, provisional quality thresholds, and a
redacted reporting contract. Live latency/cost remain report-only while replay
is the canonical deterministic gate.

## Files Modified

- `evaluation/sprint-5/metrics.md`

## Testing

- **Status:** Metric definitions are documented; executable calculation is assigned to S5-27.
- **Governance:** Threshold gate bypassed per user instruction and remains visible for final review.
