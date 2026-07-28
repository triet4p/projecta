# Task Summary: S1-02 — Draft Competency Questions

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-02 — Draft Competency Questions

## Summary of Work

Drafted 14 competency questions for the Quick Note vertical slice, each with a stable identifier (`CQ-{CATEGORY}-{NNN}`), a natural-language question in Vietnamese, and a structured expected answer shape. The questions are organized into five categories:

- **Note Retrieval (4):** CQ-NOTE-001 through CQ-NOTE-004 — listing notes in a project, retrieving author, timestamp, and project scope.
- **Note Item Retrieval (3):** CQ-NOTEITEM-001 through CQ-NOTEITEM-003 — listing items in a note with types, filtering by type, retrieving full content.
- **Author and Provenance (3):** CQ-PROV-001 through CQ-PROV-003 — notes by author, provenance chain for an item, all items captured by a person.
- **Aggregation (2):** CQ-COUNT-001 through CQ-COUNT-002 — item count by type per project, note count per project.
- **Boundary and Data Quality (2):** CQ-BOUND-001 through CQ-BOUND-002 — ASK queries detecting orphan notes and orphan note items.

Every question includes an example mapping to the positive example from [docs/use-cases/quick-note.md](../../../../docs/use-cases/quick-note.md) (BrSE Le, "Ecommerce Checkout Redesign," 6-item sprint review note).

## Files Modified

- [ontology/competency-questions/quick-note.md](../../../../ontology/competency-questions/quick-note.md) — New file: 14 competency questions with identifiers, answer shapes, and example mappings.

## Testing

- **Test Type:** Specification review (no automated test — SPARQL implementation is S1-11).
- **Validation Performed:**
  - Each question maps to at least one concrete data point in the positive example from the Quick Note use case.
  - Questions cover all Note and NoteItem properties identified in the use case boundary (§6): `belongsToProject`, `hasNoteItem`, `authoredBy`, `recordedAt`, `contentText`, `itemType`.
  - Boundary questions (CQ-BOUND-001, CQ-BOUND-002) directly enforce the counterexample constraints from the use case (no project-less notes, no orphan items).
  - The 14 questions stay within Sprint 1 scope — no candidate extraction, entity linking, inference, or confirmation workflow questions.
  - Query types cover SELECT, SELECT with GROUP BY/COUNT, and ASK — providing a representative test surface for Jena (S1-12).
- **Status:** Awaiting human review (S1-03).

## Additional Notes

- Questions use the same demo scenario ("Ecommerce Checkout Redesign") established in S1-01, ensuring consistency across the sprint.
- CQ-PROV-003 is the only cross-project query — it intentionally exercises project-context propagation through the provenance chain.
- The ASK questions (CQ-BOUND-*) are designed to validate SHACL shapes (S1-08/S1-09) can be enforced at query time, complementing the negative fixtures in S1-13.
