# Sprint 12 G1 Owner-Delegated AI Annotation Amendment

**Status:** `HUMAN_APPROVED_FOR_SYNTHETIC_AI_TRACK`

**Approved by:** Project owner in the Codex task on 2026-08-14

## Decision

The project owner delegates semantic annotation, review and adjudication of
the repository-visible synthetic pilot and development/validation corpus to
the implementation agent. All resulting cases and review records remain
`humanEvidence: false` and use `agent-authored-synthetic` provenance.

This amendment creates an executable synthetic AI-reviewed benchmark track. It
does not reinterpret agent output as human work.

## Contract changes

| G1 requirement | Amended synthetic-track rule |
| --- | --- |
| Human-authored fraction `>= 60%` | `0%`; all repository-visible generated cases are agent-authored synthetic |
| Two qualified human annotators | Replaced by two logical calibration fixtures plus one owner-delegated AI semantic review |
| Independent-human agreement | Not available and must not be claimed |
| Third human adjudicator | Replaced for the synthetic track by owner-delegated AI adjudication |
| Fresh human rerun | Replaced by a 12-case disjoint AI semantic-conformance rerun |
| Scenario/answer agreement | Not applicable without independent labels; single-review conformance is reported separately |
| Test custody | Unchanged; a real external custodian and non-reconstructible sealed bundle remain required |

## Claim boundary

The amended track may claim only that the named, digest-bound synthetic corpus
has passed deterministic integrity checks and owner-delegated AI semantic
review. It may not claim:

- inter-human agreement or qualified-human annotation reliability;
- representative tenant, language, role or domain coverage;
- target-role usefulness or manual-effort improvement;
- production-scale readiness; or
- authorization to unseal or reconstruct held-out test material.

## Semantic outcome

`NO_ONTOLOGY_CHANGE_REQUIRED`. Annotation and review provenance remain
evaluation metadata outside RDF domain truth. Released types and predicates
are reused; a released concept missing from the candidate contract is recorded
as a candidate-contract gap rather than force-fit or treated as permission to
change production ontology.
