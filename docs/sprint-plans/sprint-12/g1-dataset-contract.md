# Sprint 12 G1 Dataset Contract Review Packet

**Status:** `APPROVED`

**Sprint:** Sprint 12 — Business Semantic Quality and Evaluation

**Gate:** G1 — Dataset Contract

**Decision:** Project owner and semantic reviewer approved the frozen design
without revisions on 2026-08-14.

## 1. Decision record

| Field | Value |
| --- | --- |
| G0 prerequisite | Approved without revision in `g0-business-scope.md` |
| G1 outcome | `APPROVED` |
| Approval authority | Project owner plus semantic reviewer |
| Dataset authoring | Not yet started at scale |
| Held-out test access | Not available to the agent |
| Ontology outcome | No ontology change proposed; audit is human approved |
| Next gate | G2 — Annotation Pilot |

G1 approval authorizes contract-compliant authoring and annotation. It does not
approve the quality of any future dataset, baseline, model, ontology release or
product claim.

## 2. Contract package (S12-11 through S12-27)

| Task | Contract artifact | Review purpose |
| --- | --- | --- |
| S12-11 | `evaluation/sprint-12/schema/atomic-case.schema.json` and `scenario-case.schema.json` | Stable IDs, source envelope, origin, language, sensitivity, license, split and version |
| S12-12 | Atomic JSON Schema and annotation guide | Entities, relations, links, evidence, abstention, ambiguity and gaps |
| S12-13 | Scenario JSON Schema | Ordered events, reviews, graph checkpoints, temporal effects and grounded answers |
| S12-14 | `annotation-guide.v1.md` and scenario correction enum | Unchanged, formatting-only, minor, major, rejected and missing output |
| S12-15 | `coverage-matrix.v1.json` | Journey × type × language × style × ambiguity × temporal × threat coverage |
| S12-16 | Coverage minimums | 200 atomic cases, 24 episodes, split/language/human-origin quotas |
| S12-17 | `annotation-guide.v1.md` | Reproducible decision rules and counterexamples |
| S12-18 | Annotation guide and role policy | Qualification, independence, conflict and adjudication authority |
| S12-19/S12-20 | `data-governance.v1.md` | Provenance, permission, licensing, privacy, retention and deletion |
| S12-21/S12-22 | `data-governance.v1.md` | Duplicate/leakage threat model, split and human custody procedure |
| S12-23 | G1 validation rules below | Deterministic schema, offset, quota, provenance, duplicate and reference checks |
| S12-24 | `metrics.v1.md` | Formulas, denominators, missing outputs, confidence intervals and slices |
| S12-25 | Threshold table below | Pre-registered hard, semantic, business and operational gates |
| S12-26 | `docs/ontology/sprint-12-reuse-gap-audit.md` | Reuse/no-change outcome and semantic-gap escalation |
| S12-27 | This packet | Exact review scope and approval boundary |

## 3. Dataset envelope and splits

The atomic contract requires a stable case ID, `s12.atomic.v1`, one G0 journey,
optional scenario reference, canonical source envelope, split and atomic gold.
The scenario contract requires `s12.scenario.v1`, 5–12 ordered events, source
manifest, graph checkpoints and competency-question answers.

Minimum quotas are 200 atomic cases and 24 episodes. Atomic cases split 120/40/40
for development/validation/test. Scenarios split 12/6/6. Language minimums are
80 Vietnamese, 40 English, 20 Japanese and 20 mixed/code-switched atomic cases.
At least 60% of cases are human-authored from approved business scenarios;
model-assisted cases require human rewriting and independent annotation.

The journey minimums sum to the 200-case atomic minimum; any additional cases
must address G1-approved coverage gaps. Quotas are minimums, not permission to
omit a mandatory threat or language slice.

## 4. Annotation and adjudication contract

- Every validation/test item and at least 25% of development items receive two
  independent annotations.
- A third qualified reviewer adjudicates every material validation/test
  disagreement and records the rule/reason for the outcome.
- G2 provisional agreement targets are typed classification/abstention `>=0.80`,
  span F1 `>=0.85`, relation/link F1 `>=0.80` and scenario graph-state
  agreement `>=0.80`.
- The annotation guide is versioned. A post-G3 rule change requires a new
  dataset version and freeze.
- Unsupported concepts are semantic gaps; annotators may not add or invent
  ontology terms.

## 5. Deterministic validation rules (S12-23)

The G1 loader/validator must fail closed on:

- unknown schema/version, malformed stable IDs or duplicate IDs;
- missing source origin, license/permission, sensitivity, language, split or
  content digest;
- invalid UTF-8/canonical text or evidence offsets whose source slice does not
  equal the stored span text;
- zero/negative/reversed spans, unsupported types/predicates or unknown target
  IDs;
- relation endpoints outside the same project context, self-relations or
  links not in the bounded context;
- abstention inconsistent with a non-empty/empty gold outcome;
- semantic gap without rationale or a gold concept force-fit to an unsupported
  term;
- scenario events outside 5–12, duplicate order, missing checkpoint references,
  invalid correction classes or unbound competency questions;
- split leakage, quota/coverage shortfall, missing double annotation or absent
  adjudication for material disagreement;
- prohibited data, missing provenance/license, invalid digest or custody mismatch.

The validator must report case IDs and safe failure classes without emitting raw
source text, provider payloads, credentials or held-out gold.

## 6. Pre-registered thresholds (S12-25)

| Category | Threshold | Gate |
| --- | --- | --- |
| Hard invariants | 100% | G4/G5/G6; any failure blocks |
| Entity-type macro F1 | `>= 0.80` | G6 |
| Relation macro F1 | `>= 0.75` | G6 |
| Bounded-link F1 | `>= 0.80` | G6 |
| Evidence-span exact match | `>= 0.95` | G6 |
| Abstention precision/recall | `>= 0.90` each | G6 |
| Released-ontology mapping accuracy | `>= 0.85` on mappable gold | G6 |
| Scenario checkpoint graph accuracy | `>= 0.80` | G6 |
| Grounded answer factual correctness | `>= 0.85` | G6 |
| Citation correctness | `1.00` | G6 |
| Answer completeness | `>= 0.80` on answerable questions | G6 |
| Accepted without semantic correction | `>= 70%` | G6 |
| Accepted unchanged or minor correction | `>= 85%` | G6 |
| Review time versus manual baseline | Median at least 30% lower | G6 |
| Blinded reviewer study | 3+ roles, 12+ scenarios, usefulness/trust median `>=4/5` | G6 |

G1 freezes formulas and denominators, not observed results. These values may be
revised once before G3 with written rationale; they cannot change after G3
without invalidating the frozen benchmark.

## 7. Ontology and semantic review (S12-26)

The audit at [sprint-12-reuse-gap-audit.md](../ontology/sprint-12-reuse-gap-audit.md)
classifies released source, candidate, asserted, inferred, provenance,
temporal and retrieval semantics as reuse. Dataset identity, split, custody,
correction, metric and leakage fields remain evaluation/operational metadata.
No Turtle, SHACL, rule, migration or runtime RDF artifact is changed.

The project owner and semantic reviewer explicitly approved the no-change
outcome without revision. Any future held-out gold concept that cannot map to
released semantics must still identify the exact competency question and
reopen ontology governance.

## 8. G1 acceptance checklist

- [x] Case and scenario schemas are versioned and closed-world at the contract boundary.
- [x] Atomic and longitudinal gold semantics are defined.
- [x] Correction, review, abstention, ambiguity and semantic-gap outcomes are explicit.
- [x] Coverage matrix and minimum quotas are bound to the G0 journeys.
- [x] Annotation qualification, independence and adjudication are defined.
- [x] Provenance, licensing, privacy, retention and deletion controls are defined.
- [x] Leakage threat model, split policy and human custody procedure are defined.
- [x] Deterministic validation rules and safe failure reporting are defined.
- [x] Metric formulas, missing-output handling and reporting slices are defined.
- [x] Thresholds are pre-registered before full corpus observation.
- [x] Ontology reuse/no-change audit is approved without revision.
- [x] Project owner and semantic reviewer approve the G1 dataset contract.

## 9. Approval record (S12-28)

| Field | Value |
| --- | --- |
| G1 outcome | `APPROVED` |
| Project owner | Explicit approval recorded in Codex task on 2026-08-14 |
| Semantic reviewer | Explicit approval recorded in Codex task on 2026-08-14 |
| Approved revisions | None |
| Reviewed package | This packet, schema files, coverage matrix, guide, governance, metrics and ontology audit |
| Authorization after approval | Begin G2 pilot authoring only; no held-out access or release authorization |
