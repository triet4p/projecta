# Development Error Analysis v1

Status: `COMPLETED_OFFLINE_DEVELOPMENT_BACKLOG`

This backlog analyzes persisted S12-73, S12-77 and S12-f-06 evidence only. No provider, evaluator run, model, sampling sweep, gold change or ontology change was performed.

## Gate result

- Case/run accounting: **288/288** report executions accounted.
- Missing outputs: **17**, retained as fail-explicit records.
- Split: development only; held-out was not inspected.
- Exact entity-type and predicate/endpoints confusion: **not observable** from the persisted sanitized reports; gold denominators are included in JSON and this is routed to evaluator instrumentation.

## Main finding

Positive-relation case-runs: **86**; relation-error case-runs: **86** (100.0%). Relation contract representability is true, and the errors recur across the positive-relation evidence rather than being explained only by a zero denominator. The approved next direction is **one prompt-only relation experiment**.

## Error classes and routing

| Error class | Evidence treatment | Routing |
|---|---|---|
| missing entity | observed from per-case aggregate counts | prompt |
| unsupported entity | not observable in sanitized reports | evaluator |
| wrong entity type | not observable in sanitized reports | evaluator |
| missing relation | observed when gold relation > TP and predicted = 0 | prompt |
| wrong predicate/endpoints | inferred when gold relation > TP and a relation was predicted | prompt |
| incorrect abstention | observed from per-case abstention accuracy | prompt |
| hallucination | observed from unmatched predicted entity/count or hallucination rate | prompt |
| schema/evidence/runtime failure | observed from failure class or missing-output status | tool |

## Confusion by entity type and relation predicate

The required denominator tables are present below. Exact TP/FP/FN confusion is `n/a` because the persisted sanitized reports do not retain predicted type, predicate or endpoint pairs.

### Entity type

| Entity type | Gold items | Gold cases | TP | FP | FN |
|---|---:|---:|---:|---:|---:|
| Assumption | 1 | 1 | n/a | n/a | n/a |
| Constraint | 2 | 2 | n/a | n/a | n/a |
| Decision | 12 | 12 | n/a | n/a | n/a |
| ProgressClaim | 2 | 2 | n/a | n/a | n/a |
| Question | 2 | 2 | n/a | n/a | n/a |
| Requirement | 6 | 6 | n/a | n/a | n/a |
| ResearchFinding | 3 | 3 | n/a | n/a | n/a |
| Risk | 2 | 2 | n/a | n/a | n/a |
| Task | 6 | 6 | n/a | n/a | n/a |

### Relation predicate

| Predicate | Gold items | Gold cases | TP | FP | FN |
|---|---:|---:|---:|---:|---:|
| answers | 1 | 1 | n/a | n/a | n/a |
| constrainedBy | 1 | 1 | n/a | n/a | n/a |
| dependsOn | 3 | 3 | n/a | n/a | n/a |
| implements | 2 | 2 | n/a | n/a | n/a |
| resolves | 1 | 1 | n/a | n/a | n/a |
| supports | 2 | 2 | n/a | n/a | n/a |

## Dataset-slice error counts

Counts are case-runs, so the denominator is explicit and is not a pooled-only summary.

| Slice | Case-runs | Error counts |
|---|---:|---|
| contradiction-or-supersession | 108 | hallucination: 9, incorrect abstention: 9, schema/evidence/runtime failure: 10 |
| cross-project-isolation | 6 | none |
| duplicate-evidence | 90 | hallucination: 50, incorrect abstention: 36, missing entity: 37, missing relation: 36, schema/evidence/runtime failure: 4, wrong predicate/endpoints: 50 |
| explicit-ambiguity-or-abstention | 12 | none |
| fabricated-link | 12 | schema/evidence/runtime failure: 2 |
| temporal-change | 36 | hallucination: 23, incorrect abstention: 12, missing entity: 35, schema/evidence/runtime failure: 1 |
| unicode-and-noisy-text | 24 | hallucination: 17, incorrect abstention: 7, missing entity: 24 |

## Run-to-run variance

Population variance is computed over the persisted independent runs within each group. Full run details, latency and usage are in the JSON artifact.

| Group | Variant | Metric | Mean | Min | Max | Population variance |
|---|---|---|---:|---:|---:|---:|
| s12-73-prompt-8-case | candidate | entityMacroF1 | 0.9583 | 0.8750 | 1.0000 | 0.003472 |
| s12-73-prompt-8-case | candidate | relationMacroF1 | 1.0000 | 1.0000 | 1.0000 | 0.000000 |
| s12-73-prompt-8-case | candidate | abstentionAccuracy | 0.9583 | 0.8750 | 1.0000 | 0.003472 |
| s12-73-prompt-8-case | candidate | hallucinationRate | 0.0417 | 0.0000 | 0.1250 | 0.003472 |
| s12-73-prompt-8-case | control | entityMacroF1 | 0.5333 | 0.2000 | 0.8000 | 0.062222 |
| s12-73-prompt-8-case | control | relationMacroF1 | 1.0000 | 1.0000 | 1.0000 | 0.000000 |
| s12-73-prompt-8-case | control | abstentionAccuracy | 0.5333 | 0.2000 | 0.8000 | 0.062222 |
| s12-73-prompt-8-case | control | hallucinationRate | 0.4667 | 0.2000 | 0.8000 | 0.062222 |
| s12-73-prompt-followup-32-case | candidate | entityMacroF1 | 0.3436 | 0.3226 | 0.3750 | 0.000511 |
| s12-73-prompt-followup-32-case | candidate | relationMacroF1 | 0.7636 | 0.7500 | 0.7742 | 0.000102 |
| s12-73-prompt-followup-32-case | candidate | abstentionAccuracy | 0.6564 | 0.6250 | 0.6774 | 0.000511 |
| s12-73-prompt-followup-32-case | candidate | hallucinationRate | 0.3555 | 0.2917 | 0.4194 | 0.002717 |
| s12-77-model-16-case | candidate | entityMacroF1 | 0.7550 | 0.6667 | 0.8125 | 0.004017 |
| s12-77-model-16-case | candidate | relationMacroF1 | 0.5558 | 0.5333 | 0.5714 | 0.000265 |
| s12-77-model-16-case | candidate | abstentionAccuracy | 0.8218 | 0.7333 | 0.8750 | 0.003969 |
| s12-77-model-16-case | candidate | hallucinationRate | 0.1556 | 0.1333 | 0.1667 | 0.000247 |
| s12-77-model-16-case | control | entityMacroF1 | 0.7785 | 0.7188 | 0.8667 | 0.004052 |
| s12-77-model-16-case | control | relationMacroF1 | 0.5528 | 0.5333 | 0.5625 | 0.000189 |
| s12-77-model-16-case | control | abstentionAccuracy | 0.8319 | 0.7500 | 0.9333 | 0.005791 |
| s12-77-model-16-case | control | hallucinationRate | 0.1500 | 0.1042 | 0.2000 | 0.001539 |
| s12-f-06-sampling-8-case | candidate | entityMacroF1 | 0.6667 | 0.6250 | 0.7500 | 0.003472 |
| s12-f-06-sampling-8-case | candidate | relationMacroF1 | 0.5000 | 0.5000 | 0.5000 | 0.000000 |
| s12-f-06-sampling-8-case | candidate | abstentionAccuracy | 0.7917 | 0.7500 | 0.8750 | 0.003472 |
| s12-f-06-sampling-8-case | candidate | hallucinationRate | 0.2222 | 0.2083 | 0.2500 | 0.000386 |
| s12-f-06-sampling-8-case | control | entityMacroF1 | 0.7381 | 0.7143 | 0.7500 | 0.000283 |
| s12-f-06-sampling-8-case | control | relationMacroF1 | 0.5238 | 0.5000 | 0.5714 | 0.001134 |
| s12-f-06-sampling-8-case | control | abstentionAccuracy | 0.8690 | 0.8571 | 0.8750 | 0.000071 |
| s12-f-06-sampling-8-case | control | hallucinationRate | 0.2460 | 0.2381 | 0.2500 | 0.000031 |

## Recurring versus stochastic

A case/error pair observed in at least two independent persisted runs is marked recurring; one occurrence is marked stochastic one-off. A clean targeted diagnostic remains non-reproduction, not resolution.

| Group | Variant | Case | Error | Runs | Pattern |
|---|---|---|---|---:|---|
| s12-73-prompt-8-case | candidate | s12-a-0154 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-8-case | candidate | s12-a-0154 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0106 | hallucination | 2 | recurring |
| s12-73-prompt-8-case | control | s12-a-0106 | incorrect abstention | 2 | recurring |
| s12-73-prompt-8-case | control | s12-a-0122 | schema/evidence/runtime failure | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0130 | hallucination | 2 | recurring |
| s12-73-prompt-8-case | control | s12-a-0130 | incorrect abstention | 2 | recurring |
| s12-73-prompt-8-case | control | s12-a-0138 | schema/evidence/runtime failure | 3 | recurring |
| s12-73-prompt-8-case | control | s12-a-0154 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0154 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0154 | schema/evidence/runtime failure | 2 | recurring |
| s12-73-prompt-8-case | control | s12-a-0162 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0162 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0162 | schema/evidence/runtime failure | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0178 | schema/evidence/runtime failure | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0186 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0186 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-8-case | control | s12-a-0186 | schema/evidence/runtime failure | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0105 | hallucination | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0105 | wrong predicate/endpoints | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0107 | hallucination | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0107 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0107 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0108 | hallucination | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0108 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0121 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0121 | incorrect abstention | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0121 | missing entity | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0121 | missing relation | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0121 | wrong predicate/endpoints | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0122 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0122 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0123 | hallucination | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0123 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0123 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0124 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0124 | incorrect abstention | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0124 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0129 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0129 | incorrect abstention | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0129 | missing entity | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0129 | missing relation | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0129 | wrong predicate/endpoints | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0131 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0131 | incorrect abstention | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0131 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0132 | hallucination | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0132 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0132 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0137 | incorrect abstention | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0137 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0137 | missing relation | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0153 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0153 | schema/evidence/runtime failure | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0153 | wrong predicate/endpoints | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0155 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0155 | incorrect abstention | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0155 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0156 | hallucination | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0156 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0161 | hallucination | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0161 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0161 | missing entity | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0161 | missing relation | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0161 | wrong predicate/endpoints | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0163 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0163 | incorrect abstention | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0163 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0164 | hallucination | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0164 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0177 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0177 | incorrect abstention | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0177 | missing entity | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0177 | missing relation | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0177 | wrong predicate/endpoints | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0179 | hallucination | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0179 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0179 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0180 | hallucination | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0180 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0180 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0185 | incorrect abstention | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0185 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0185 | missing relation | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0187 | hallucination | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0187 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0187 | missing entity | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0187 | schema/evidence/runtime failure | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0188 | hallucination | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0188 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0203 | hallucination | 2 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0203 | incorrect abstention | 1 | stochastic_one_off |
| s12-73-prompt-followup-32-case | candidate | s12-a-0203 | missing entity | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0204 | incorrect abstention | 3 | recurring |
| s12-73-prompt-followup-32-case | candidate | s12-a-0204 | missing entity | 3 | recurring |
| s12-77-model-16-case | candidate | s12-a-0105 | hallucination | 2 | recurring |
| s12-77-model-16-case | candidate | s12-a-0105 | incorrect abstention | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0105 | missing entity | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0105 | missing relation | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0105 | wrong predicate/endpoints | 2 | recurring |
| s12-77-model-16-case | candidate | s12-a-0121 | hallucination | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0121 | incorrect abstention | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0121 | missing entity | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0121 | missing relation | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0121 | schema/evidence/runtime failure | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0121 | wrong predicate/endpoints | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0153 | hallucination | 3 | recurring |
| s12-77-model-16-case | candidate | s12-a-0153 | wrong predicate/endpoints | 3 | recurring |
| s12-77-model-16-case | candidate | s12-a-0161 | hallucination | 3 | recurring |
| s12-77-model-16-case | candidate | s12-a-0161 | wrong predicate/endpoints | 3 | recurring |
| s12-77-model-16-case | candidate | s12-a-0176 | schema/evidence/runtime failure | 2 | recurring |
| s12-77-model-16-case | candidate | s12-a-0177 | hallucination | 2 | recurring |
| s12-77-model-16-case | candidate | s12-a-0177 | incorrect abstention | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0177 | missing entity | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0177 | missing relation | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0177 | wrong predicate/endpoints | 2 | recurring |
| s12-77-model-16-case | candidate | s12-a-0187 | hallucination | 3 | recurring |
| s12-77-model-16-case | candidate | s12-a-0187 | missing entity | 3 | recurring |
| s12-77-model-16-case | candidate | s12-a-0201 | hallucination | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0201 | incorrect abstention | 2 | recurring |
| s12-77-model-16-case | candidate | s12-a-0201 | missing entity | 2 | recurring |
| s12-77-model-16-case | candidate | s12-a-0201 | missing relation | 2 | recurring |
| s12-77-model-16-case | candidate | s12-a-0201 | wrong predicate/endpoints | 1 | stochastic_one_off |
| s12-77-model-16-case | candidate | s12-a-0233 | incorrect abstention | 3 | recurring |
| s12-77-model-16-case | candidate | s12-a-0233 | missing entity | 3 | recurring |
| s12-77-model-16-case | candidate | s12-a-0233 | missing relation | 3 | recurring |
| s12-77-model-16-case | control | s12-a-0105 | hallucination | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0105 | incorrect abstention | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0105 | missing entity | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0105 | missing relation | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0105 | wrong predicate/endpoints | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0121 | hallucination | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0121 | incorrect abstention | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0121 | missing entity | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0121 | missing relation | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0121 | wrong predicate/endpoints | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0153 | hallucination | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0153 | incorrect abstention | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0153 | missing entity | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0153 | missing relation | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0153 | wrong predicate/endpoints | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0161 | hallucination | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0161 | incorrect abstention | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0161 | missing entity | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0161 | missing relation | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0161 | wrong predicate/endpoints | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0177 | hallucination | 3 | recurring |
| s12-77-model-16-case | control | s12-a-0177 | wrong predicate/endpoints | 3 | recurring |
| s12-77-model-16-case | control | s12-a-0187 | hallucination | 2 | recurring |
| s12-77-model-16-case | control | s12-a-0187 | incorrect abstention | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0187 | missing entity | 3 | recurring |
| s12-77-model-16-case | control | s12-a-0201 | incorrect abstention | 3 | recurring |
| s12-77-model-16-case | control | s12-a-0201 | missing entity | 3 | recurring |
| s12-77-model-16-case | control | s12-a-0201 | missing relation | 3 | recurring |
| s12-77-model-16-case | control | s12-a-0226 | schema/evidence/runtime failure | 1 | stochastic_one_off |
| s12-77-model-16-case | control | s12-a-0233 | hallucination | 3 | recurring |
| s12-77-model-16-case | control | s12-a-0233 | wrong predicate/endpoints | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0121 | hallucination | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0121 | wrong predicate/endpoints | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0153 | hallucination | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0153 | wrong predicate/endpoints | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0187 | hallucination | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0187 | missing entity | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0201 | incorrect abstention | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0201 | missing entity | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0201 | missing relation | 3 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0233 | hallucination | 1 | stochastic_one_off |
| s12-f-06-sampling-8-case | candidate | s12-a-0233 | incorrect abstention | 2 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0233 | missing entity | 2 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0233 | missing relation | 2 | recurring |
| s12-f-06-sampling-8-case | candidate | s12-a-0233 | wrong predicate/endpoints | 1 | stochastic_one_off |
| s12-f-06-sampling-8-case | control | s12-a-0121 | hallucination | 1 | stochastic_one_off |
| s12-f-06-sampling-8-case | control | s12-a-0121 | incorrect abstention | 2 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0121 | missing entity | 2 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0121 | missing relation | 2 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0121 | wrong predicate/endpoints | 1 | stochastic_one_off |
| s12-f-06-sampling-8-case | control | s12-a-0153 | hallucination | 2 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0153 | schema/evidence/runtime failure | 1 | stochastic_one_off |
| s12-f-06-sampling-8-case | control | s12-a-0153 | wrong predicate/endpoints | 2 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0187 | hallucination | 3 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0187 | missing entity | 3 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0201 | hallucination | 2 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0201 | incorrect abstention | 1 | stochastic_one_off |
| s12-f-06-sampling-8-case | control | s12-a-0201 | missing entity | 1 | stochastic_one_off |
| s12-f-06-sampling-8-case | control | s12-a-0201 | missing relation | 1 | stochastic_one_off |
| s12-f-06-sampling-8-case | control | s12-a-0201 | wrong predicate/endpoints | 2 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0233 | hallucination | 3 | recurring |
| s12-f-06-sampling-8-case | control | s12-a-0233 | wrong predicate/endpoints | 3 | recurring |

## Common-case denominators

- `s12-73-prompt-8-case`: `{"commonCaseExecutionCount": 15, "groupId": "s12-73-prompt-8-case", "method": "paired_intersection_of_valid_outputs", "pairedRuns": [{"candidateScored": 8, "commonCaseCount": 5, "controlScored": 5, "run": "01"}, {"candidateScored": 8, "commonCaseCount": 5, "controlScored": 5, "run": "02"}, {"candidateScored": 8, "commonCaseCount": 5, "controlScored": 5, "run": "03"}]}`
- `s12-73-prompt-followup-32-case`: `{"allRunCommonCaseCount": 30, "groupId": "s12-73-prompt-followup-32-case", "method": "intersection_across_independent_runs", "perRunScoredCounts": [30, 32, 31]}`
- `s12-77-model-16-case`: `{"commonCaseExecutionCount": 44, "groupId": "s12-77-model-16-case", "method": "paired_intersection_of_valid_outputs", "pairedRuns": [{"candidateScored": 14, "commonCaseCount": 13, "controlScored": 15, "run": "01"}, {"candidateScored": 15, "commonCaseCount": 15, "controlScored": 16, "run": "02"}, {"candidateScored": 16, "commonCaseCount": 16, "controlScored": 16, "run": "03"}]}`
- `s12-f-06-sampling-8-case`: `{"commonCaseExecutionCount": 23, "groupId": "s12-f-06-sampling-8-case", "method": "paired_intersection_of_valid_outputs", "pairedRuns": [{"candidateScored": 8, "commonCaseCount": 7, "controlScored": 7, "run": "01"}, {"candidateScored": 8, "commonCaseCount": 8, "controlScored": 8, "run": "02"}, {"candidateScored": 8, "commonCaseCount": 8, "controlScored": 8, "run": "03"}]}`

## S12-f-07 decision

- Status: **PREREGISTERED_NOT_EXECUTED**.
- Control: `m3.prompt.v3.supersession-guard`; candidate: `m3.prompt.v4.relation-decision-rubric`.
- Model: `deepseek-v4-flash`; sampling: `provider-default`.
- Stage A: 16 development cases × 3 paired runs, no retry. The selected cases contain positive relations, hard negatives/semantic gaps, and abstention/isolation cases.
- Stage B: 32 × 3 is closed unless Stage A has zero schema/evidence/missing-output failures, relation macro F1 at least +0.05, no more than 0.01 entity or abstention decrease, no hallucination increase, and latency/usage accounted.
- Do not run `deepseek-v4-pro`; do not run a sampling sweep. Validation, full 160, candidate freeze and held-out remain locked.

## Artifact limits

The sanitized reports preserve aggregate TP/predicted/gold counts but not predicted entity types, relation predicates or endpoint pairs. Therefore the JSON includes the gold denominator tables with null TP/FP/FN cells and an explicit evaluator-instrumentation gap. No exact confusion claim is made.

See [development-error-analysis.v1.json](./development-error-analysis.v1.json) for every case/run record, source digests, failures, latency, usage, denominators and the preregistered next experiment.
