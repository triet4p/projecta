# Sprint 12 G2 Annotation Pilot Review Packet

**Status:** `G2_APPROVED_G3_PENDING`

**Gate:** G2 — Annotation Pilot

**Decision:** G2 is approved by the project owner for progression to G3
preparation, with the evidence limitations below explicitly retained. Human
annotation evidence and a fresh rerun remain required before any claim of
qualified annotator reliability or production-scale readiness.

## 1. Decision record

| Field | Value |
| --- | --- |
| G0 | Approved without revision |
| G1 | Approved without revision |
| G2 outcome | `APPROVED_WITH_LIMITATIONS` |
| Pilot corpus | 20 atomic cases and 3 five-event synthetic episodes |
| Fixture status | Agent-generated calibration fixture; not human evidence |
| Human annotators | Not yet recorded |
| Next gate if approved | G3 — Dataset Freeze |

S12-38 prepared the draft packet. The package is
executable as a calibration fixture and exposes the required evidence shapes,
disagreements and guide revisions; it does not claim that qualified human
annotators have met the G2 agreement thresholds.

## 2. Pilot package

| Artifact | Purpose | Status |
| --- | --- | --- |
| `pilot/atomic-pilot.v1.json` | 20 synthetic cases spanning released types, multilingual text, ambiguity, gaps, hostile input, isolation and noisy text | Prepared |
| `pilot/scenario-pilot.v1.json` | Three five-event episodes with checkpoints and grounded questions | Prepared |
| `pilot/calibration-protocol.v1.md` | Qualification, common examples, isolation and conflict procedure | Prepared |
| `pilot/labels/annotator-a.v1.json` | Isolated fixture label set A | Fixture only |
| `pilot/labels/annotator-b.v1.json` | Isolated fixture label set B | Fixture only |
| `pilot/agreement-report.v1.json` | Type, span, relation/link, abstention, graph and QA agreement | Fixture only |
| `pilot/adjudication-log.v1.json` | Two controlled disagreements and accepted outcomes | Fixture only |
| `pilot/annotation-guide.v1.1.md` | Two guide revisions from calibration disagreement | Proposed |

## 3. Fixture validation and provisional results

The fixture has 20 cases, three scenarios, real source content digests, no
restricted payload and exact evidence slices. Label sets are isolated in the
artifact structure and deliberately disagree on two cases so adjudication and
guide revision are exercised.

| Metric | Fixture result | Provisional G2 target | Interpretation |
| --- | ---: | ---: | --- |
| Type/abstention agreement | 0.90 | 0.80 | Fixture passes; human evidence absent |
| Span F1 | 0.97297 | 0.85 | Recomputed from 18/19 spans; human evidence absent |
| Relation/link F1 | 1.00 | 0.80 | Fixture passes; human evidence absent |
| Scenario graph-state agreement | N/A | 0.80 | No independent scenario labels supplied |
| Question-answer agreement | N/A | Report | No independent competency-answer labels supplied |

The report is bound to its two fixture label sets and deliberately does not
invent scenario or question-answer agreement values. The fixture therefore
does not pass the complete provisional gate, even though its recomputed
type/abstention, span and relation/link dimensions are diagnostic.

### Known preparation blockers

- [x] Scenario fixtures include the required `sourceManifest` field and the
  contract test validates the actual instance shape.
- [x] The context-free `s12-a-0009` gold outcome is abstention under AG-01.
- [ ] Qualified human calibration and independent annotation are supplied.
- [ ] A qualified reviewer adjudicates the human disagreements.
- [ ] A fresh subset is rerun after guide revision.

These limitations are accepted as explicit residual risks for this approval;
they do not convert synthetic fixture evidence into human evidence.

## 4. Human evidence required for G2

Before any claim of qualified annotator reliability or production-scale
readiness, the annotation lead must:

- identify qualified Vietnamese, English, Japanese and mixed-language
  annotators for the slices actually retained;
- run calibration examples without exposing pilot labels or future held-out
  gold;
- produce two independently labeled pilot sets under separate custody;
- record conflicts, language/domain qualification and annotation versions;
- compute agreement with the G1 metric contract;
- have a qualified third reviewer adjudicate every material disagreement;
- rerun the revised guide on a fresh calibration subset; and
- preserve all disagreements, failed slices and guide revisions.

The agent fixture may be retained as a regression test but must not be counted
as the human pilot result.

## 5. G2 acceptance checklist

- [x] Pilot atomic set has at least 20 synthetic cases.
- [x] Pilot scenario set has at least 3 longitudinal episodes with schema-valid
  source manifests.
- [x] Pilot provenance, licensing, sensitivity and content digests are fully
  validated for the scenario instances.
- [x] Calibration protocol and role separation are defined.
- [x] Two isolated label-set fixtures exist and are intentionally non-identical.
- [ ] Human agreement metrics and provisional thresholds are computed.
- [ ] Human disagreements have accepted outcomes and guide revisions.
- [ ] Fresh-rerun procedure is executed on a fresh subset.
- [ ] Qualified human annotation evidence is supplied.
- [x] Project owner approves G2 annotation reliability with the limitations
  recorded above.

## 6. Approval record (S12-39)

| Field | Value |
| --- | --- |
| G2 outcome | `APPROVED_WITH_LIMITATIONS` |
| Project owner | Explicit approval recorded in Codex task on 2026-08-14 |
| Annotation lead | _Awaiting qualified human evidence_ |
| Semantic reviewer | Limitation retained; no new ontology change approved |
| Approved revisions | Evidence limitation recorded; no contract/ontology revision |
| Authorization after approval | Proceed to G3 preparation only; do not claim qualified human reliability or unseal held-out test |
