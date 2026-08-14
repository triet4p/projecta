# Sprint 12 Metric Contract v1

**Status:** `G4_APPROVED_WITH_LIMITATIONS_G5_PENDING`

Metrics are computed per split, journey, language, semantic slice, origin and
threat slice before any pooled summary. Missing, malformed, abstained and
omitted outputs remain visible.

## Hard invariants

Every evaluated run must report a boolean result for:

- schema validity and bounded output;
- exact source/code-point evidence integrity;
- allowlisted types/predicates and server-owned target IDs;
- project isolation and no cross-project existence disclosure;
- source, candidate, activity and decision provenance;
- SHACL conformance for persisted positive cases;
- no extraction-time write to asserted/inferred graphs;
- fail-explicit behavior with no partial semantic mutation; and
- dataset provenance, split integrity, digest binding and holdout non-leakage.

Any hard-invariant failure blocks the gate; aggregate quality cannot offset it.

## Semantic metrics

| Metric | Unit and formula | Required slice/reporting |
| --- | --- | --- |
| Entity-type macro F1 | Macro average of exact `(case, span, released type)` F1 across present types | Journey, language, type, ambiguity/threat slice |
| Relation macro F1 | Macro average of exact `(case, predicate, source, target, span)` F1 | Journey, predicate, temporal/contradiction slice |
| Bounded-link F1 | Exact target and evidence span match for valid in-project links | Journey, language, same-project and negative slices |
| Evidence exact match | Fraction of gold spans with exact start/end and source-slice equality | Overall and Unicode/noisy slice |
| Abstention precision/recall | Correct required-abstention decisions divided by predicted/gold abstentions | Ambiguous, unsupported, hostile and isolation slices |
| Ontology mapping accuracy | Correct released-term mapping among mappable gold concepts | Type, journey and semantic-gap slice |
| Scenario graph accuracy | Exact checkpoint state agreement over source/candidate/asserted/inferred/provenance expectations | Episode and checkpoint |
| Answer factual correctness | Gold-supported facts / returned factual claims, with explicit answer status | Question, journey and freshness slice |
| Citation correctness | Correct source citation for every returned fact | Question and checkpoint |
| Answer completeness | Gold-supported required facts returned / required facts | Answerable questions; report partial/abstain separately |

Macro averaging is defined before observing the full corpus. Empty classes are
reported as `not-applicable` rather than silently converted to zero or removed
from a pooled score.

## Business and operational metrics

- Candidate acceptance unchanged, minor correction, major correction, rejected
  and missing output rates.
- Median and P95 review time under the Projecta workflow and matched manual
  baseline, with the same material and role protocol.
- Reviewer usefulness and trust on a five-point blinded scale.
- P50/P95 latency, input/output/reasoning tokens, configured cost, abstention
  rate and cost per accepted candidate by slice/configuration.
- Failure class, retry count and partial-mutation count; hidden retries are not
  allowed.

Confidence intervals use a pre-registered bootstrap or exact method appropriate
to the metric and unit of independence. Cases, not individual spans, are the
default resampling unit for atomic metrics; episodes are the unit for scenario
and reviewer metrics.

## Missing-output handling

Malformed or missing output is a scored failure for applicable semantic and
hard-invariant metrics, not a dropped case. A deliberate, valid abstention is
scored against abstention gold. A system error is reported separately and
remains included in denominator counts.

## Evidence report

Each report must bind dataset manifest, split, code, ontology, prompt, model,
tool, configuration and evaluator digests. It must include counts and results
for every declared slice, zero-result slices, failed cases, abstentions,
missing outputs, latency, tokens, cost and error taxonomy. Reports must exclude
raw source text, provider payloads, credentials and unapproved identifiers.
