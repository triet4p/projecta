# Sprint 5 Evaluation Metrics and Thresholds

**Dataset:** `s5.v1`
**Contract:** `m3.v1`
**Status:** APPROVED_AND_ENFORCED (2026-08-02)

## Metrics

| Metric | Definition | Required reporting |
|---|---|---|
| Schema validity | Fraction of model/replay outputs accepted by the versioned Pydantic contract before semantic normalization | Overall and by slice; target 100% for replay fixtures |
| Entity type precision/recall/F1 | Exact match on `(case, evidence span, allowlisted type)` | Overall and each supported type |
| Relation precision/recall/F1 | Exact match on `(case, predicate, source ID, target ID, evidence span)` | Overall and each predicate |
| Exact-span score | Fraction of gold spans whose start, end, and recomputed text all match exactly | Overall and Unicode slice |
| Link accuracy | Fraction of gold bounded links with exact target ID and evidence span | Same-project and negative cross-project slices |
| Abstention quality | Precision of abstentions on empty/ambiguous/adversarial cases and recall of required abstentions | By abstention slice |
| Calibration | Brier score and expected calibration error over accepted confidence values, reported as proposal-score diagnostics only | Overall and by output category |
| Latency | p50/p95 wall-clock time from gateway request to normalized response, excluding human review | Replay and opt-in live reports separately |
| Cost | Provider-reported input/output tokens and configured price calculation per case/run | Never required for replay; no raw prompt/note in report |

## Provisional Thresholds

- Replay schema validity: `100%`.
- Replay exact-span score: `100%`.
- Replay cross-project/fabricated-link rejection: `100%`.
- Replay no-persistence-on-failure: `100%`.
- Supported entity/relation/link micro-F1: `>= 0.85` on the versioned dataset.
- Abstention precision on adversarial and cross-project-negative slices: `1.00`.
- Abstention recall on explicit empty/ambiguous gold cases: `>= 0.90`.
- Live latency and cost: report-only in S5; no canonical CI pass/fail gate.

Thresholds are evaluated per dataset version and slice, not only as a pooled
average. A failing schema, safety, evidence, isolation, or transaction metric
blocks release regardless of aggregate F1. Confidence is not treated as
probability of truth and cannot auto-confirm or auto-assert a candidate.

## Reporting Contract

Reports contain dataset/contract/prompt/model versions, counts, metric values,
latency/token/cost aggregates, and error classes. They exclude raw notes,
provider payloads, credentials, arbitrary IDs outside synthetic fixtures, and
full prompts. Live evaluation is opt-in and never a prerequisite for replay CI.
