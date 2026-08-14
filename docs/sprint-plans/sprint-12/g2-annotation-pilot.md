# Sprint 12 G2 Annotation Pilot Review Packet

**Status:** `READY_FOR_HUMAN_APPROVAL`

**Gate:** G2 — Annotation Pilot

**Decision requested:** Human annotation lead and project owner must accept,
revise or reject the pilot reliability evidence before scaled corpus
production.

## 1. Decision record

| Field | Value |
| --- | --- |
| G0 | Approved without revision |
| G1 | Approved without revision |
| G2 outcome | `PENDING_HUMAN_APPROVAL` |
| Pilot corpus | 20 atomic cases and 3 five-event synthetic episodes |
| Fixture status | Agent-generated calibration fixture; not human evidence |
| Human annotators | Not yet recorded |
| Next gate if approved | G3 — Dataset Freeze |

The pilot package is executable as a calibration fixture and exposes all
required evidence shapes, disagreements and guide revisions. It does not claim
that qualified human annotators have met the G2 agreement thresholds.

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
| Span F1 | 1.00 | 0.85 | Fixture passes; human evidence absent |
| Relation/link F1 | 1.00 | 0.80 | Fixture passes; human evidence absent |
| Scenario graph-state agreement | 0.90 | 0.80 | Fixture passes; human evidence absent |
| Question-answer agreement | 0.90 | Report | Fixture diagnostic only |

## 4. Human evidence required for G2

Before approval, the annotation lead must:

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
- [x] Pilot scenario set has at least 3 longitudinal episodes.
- [x] Pilot provenance, licensing, sensitivity and content digests are present.
- [x] Calibration protocol and role separation are defined.
- [x] Two isolated label-set fixtures exist and are intentionally non-identical.
- [x] Agreement metrics and provisional thresholds are computed.
- [x] Fixture disagreements have accepted outcomes and guide revisions.
- [x] Fresh-rerun procedure is defined.
- [ ] Qualified human annotation evidence is supplied.
- [ ] Human reviewers approve G2 annotation reliability.

## 6. Approval record (S12-39)

| Field | Value |
| --- | --- |
| G2 outcome | `PENDING_HUMAN_APPROVAL` |
| Project owner | _Awaiting review_ |
| Annotation lead | _Awaiting qualified human evidence_ |
| Semantic reviewer | _Awaiting review_ |
| Approved revisions | _None recorded_ |
| Authorization after approval | Begin scaled development-pool authoring only; held-out test remains sealed |
