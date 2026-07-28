# Task Summary: S2-02 — Draft Lifecycle Competency Questions

**Sprint:** Sprint 2 — Governed Knowledge Lifecycle
**Task:** S2-02 — Draft Lifecycle Competency Questions

## Summary of Work

Drafted 19 competency questions for the Knowledge Lifecycle slice, each with a stable identifier (`CQ-{CATEGORY}-{NNN}`), a natural-language question in Vietnamese, and a structured expected answer shape. The questions are organized into five categories:

- **Knowledge Status (3):** CQ-LC-001 through CQ-LC-003 — current status of a candidate, candidates in a given lifecycle state, full lifecycle history with chronological transitions reconstructed from the provenance graph. CQ-LC-003 explicitly exercises temporal history without overwrite by deriving the lifecycle timeline from individual provenance activities rather than a single mutable status field.
- **Evidence and Source Traceability (3):** CQ-EV-001 through CQ-EV-003 — source evidence for a candidate (tracing back to NoteItem, Note, and original author), full provenance chain from asserted fact through candidate and extraction activity to source, and generator/model identity with ontology version.
- **Reviewer and Review Decision (3):** CQ-REV-001 through CQ-REV-003 — review decision with reviewer identity and timestamp, rejection reason for rejected candidates, and aggregation of all review decisions by a specific reviewer within a project.
- **Current and Historical View (4):** CQ-TEMP-001 through CQ-TEMP-004 — current asserted facts excluding superseded/retracted, historical lifecycle view of a fact, facts superseded within a time window, and temporal validity interval (`validFrom`/`validTo`) with a derived `isCurrent` flag.
- **Graph Isolation (3):** CQ-ISO-001 through CQ-ISO-003 — ASK queries detecting candidates in the asserted graph and asserted facts in the candidates graph, plus a SELECT query verifying that every state transition beyond `Extracted` has a corresponding provenance activity.
- **Project Scope (3):** CQ-SCOPE-001 through CQ-SCOPE-003 — all lifecycle entities belonging to a project with their graph locations, detection of lifecycle entities without project assignment (ASK), and detection of cross-project provenance links without authorization.

An additional "Deferred Questions" section lists 6 question patterns that were considered but explicitly excluded because they require API, UI, multi-model comparison, ranking, or inference execution capabilities outside Sprint 2 scope.

Every question includes an example mapping to the positive example from [docs/use-cases/knowledge-lifecycle.md](../../../../docs/use-cases/knowledge-lifecycle.md) (BrSE Le, "Ecommerce Checkout Redesign," address confirmation requirement).

## Files Modified

- [ontology/competency-questions/lifecycle.md](../../../../ontology/competency-questions/lifecycle.md) — New file: 19 competency questions with identifiers, answer shapes, example mappings, and deferred question patterns.

## Testing

- **Test Type:** Specification review (no automated test — SPARQL implementation is S2-15).
- **Validation Performed:**
  - Each question maps to at least one concrete data point in the positive example from the Knowledge Lifecycle use case, ensuring the questions are grounded in a realistic scenario.
  - Questions cover all seven required domains from the Sprint 2 task description: knowledge status (CQ-LC-*), evidence (CQ-EV-*), reviewer (CQ-REV-*), current view (CQ-TEMP-001, CQ-TEMP-004), history view (CQ-TEMP-002, CQ-TEMP-003), graph isolation (CQ-ISO-*), project scope (CQ-SCOPE-*), and temporal validity (CQ-TEMP-*).
  - Graph isolation questions (CQ-ISO-001, CQ-ISO-002) directly enforce the candidate/asserted separation mandated by the sprint plan's Definition of Done.
  - Temporal history questions (CQ-LC-003, CQ-TEMP-002) validate the "no overwrite" principle — history is reconstructed from provenance activities, not mutable status triples.
  - Project scope questions (CQ-SCOPE-*) enforce single-project containment and detect unauthorized cross-project provenance.
  - Query types cover SELECT (16) and ASK (3) — providing a comprehensive test surface for Jena SHACL and SPARQL validation (S2-15, S2-16).
  - The deferred questions section explicitly justifies why six question patterns are out of scope, preventing scope creep into API, UI, or extraction concerns.
- **Status:** Awaiting human review (S2-03).

## Additional Notes

- The question count (19) slightly exceeds the task's 12–18 nominal range due to the richness of the five-domain coverage. The three isolation questions and three scope questions are compact ASK/SELECT patterns that share common graph-traversal logic — if reduction is needed during S2-03 review, CQ-ISO-003 (missing provenance) and CQ-SCOPE-001 (all entities in project) are the weakest candidates for deferral.
- CQ-ISO-003 is the most complex question in the set — it requires a NOT-EXISTS or MINUS pattern to detect candidates whose state is beyond `Extracted` but lack a corresponding provenance activity. This exercises a SPARQL pattern not present in Sprint 1 queries.
- The provenance chain question (CQ-EV-002) exercises multi-hop `prov:wasDerivedFrom` traversal across three named graphs (asserted → candidates → sources), which is new graph-pattern complexity relative to Sprint 1.
- All questions assume the five named-graph model from the sprint plan; the concrete graph IRIs will be finalized in S2-10 (named-graph contract).
