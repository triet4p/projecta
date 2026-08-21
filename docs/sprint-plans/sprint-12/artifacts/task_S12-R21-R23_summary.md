# S12-R21–R23 — S12-f-09 Stage A authorization and decision

## Outcome

S12-f-09 Stage A was explicitly authorized and executed once against the
preregistered frozen v3 development subset. The run preserved all six
interleaved arm reports: 48 cases × 3 runs per arm = 288 case-runs. No retry,
validation access, test access, or Stage B authorization occurred.

The candidate is rejected for Stage B:

`STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B`

## Bound scope

- Model: `deepseek-v4-flash` for both arms.
- Prompt: `m3.prompt.v3.supersession-guard` for both arms.
- Changed dimension: `tool` only.
- Control tool: `llm-authored-relation-evidence-legacy`.
- Candidate tool: `server-owned-relation-evidence.v1`.
- Dataset: `s12.corpus.atomic.v3.frozen`, development split only.
- Retry policy: `none`.
- Cost ceiling: `$10.00`; observed bound cost: `$0.0112600264`.

## Repaired metric result

The raw execution aggregate v1 contained an offline aggregation defect: cases
with zero semantic relation true positives were represented as numeric zero for
evidence metrics instead of `not-applicable`. The raw six run reports remain
immutable. A v2 report was generated offline from those reports using the
metric-contract denominator rules.

Candidate v2 metrics:

- Relation semantic micro F1: `0.0377358491` (`1/35` semantic true positives,
  `18` predicted).
- Relation evidence support: `1.0` on applicable semantic matches.
- Relation evidence exact: `1.0` on applicable semantic matches.
- Entity macro F1: `0.2261574074`.
- Abstention accuracy: `0.6319444444`.
- Hallucination rate: `0.5260416667`.
- Hard gate: failed because candidate had 3 schema-invalid case-runs and the
  control had 8 hard failures across schema, normalization, evidence and
  isolation categories.
- Supersession false positives: `0`.

The result is therefore not eligible for Stage B. Slice floors were not
claimed because per-case slice labels are not bound in the current f09
preregistration; this is an additional measurement follow-up, not a reason to
inspect validation or rerun the provider.

## Artifacts

- Authorization: [`s12-f-09-authorization.v1.json`](../../../../evaluation/sprint-12/optimization/s12-f-09-authorization.v1.json)
- Raw execution aggregate: [`s12-f-09-relation-evidence-stage-a.v1.json`](../../../../evaluation/sprint-12/optimization/s12-f-09-relation-evidence-stage-a.v1.json)
- Repaired decision report: [`s12-f-09-relation-evidence-stage-a.v2.json`](../../../../evaluation/sprint-12/optimization/s12-f-09-relation-evidence-stage-a.v2.json)
- Immutable run directory: [`s12-f-09-relation-evidence-stage-a`](../../../../evaluation/sprint-12/optimization/s12-f-09-relation-evidence-stage-a)
- Runner: [`run_sprint12_f09_relation_evidence.py`](../../../../scripts/run_sprint12_f09_relation_evidence.py)
- Offline repair: [`repair_sprint12_f09_stage_a_report.py`](../../../../scripts/repair_sprint12_f09_stage_a_report.py)

No provider call remains authorized after this decision, and no held-out data
was inspected.
