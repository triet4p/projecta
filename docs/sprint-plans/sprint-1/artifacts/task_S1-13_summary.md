# Task Summary: S1-13 — Add Negative Fixtures

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-13 — Add Negative Fixtures

## Summary of Work

Created three negative TriG fixtures and corresponding SPARQL ASK detection queries that prove data-quality violations are detectable within Sprint 1 scope. Each fixture deliberately violates one ontology constraint; each detection query returns `TRUE` on the violation and `FALSE` on the clean demo graph.

| Fixture | Violation | Detection Query | Clean Demo | Negative Fixture |
|---|---|---|---|---|
| `negative-orphan-noteitem.trig` | NoteItem without parent Note (no `hasNoteItem`/`isItemOf`) | NEG-ORPHAN-NOTEITEM | FALSE ✓ | TRUE ✓ |
| `negative-missing-project.trig` | Note without `belongsToProject` | NEG-MISSING-PROJECT | FALSE ✓ | TRUE ✓ |
| `negative-invalid-itemtype.trig` | NoteItem `hasItemType` pointing to Person instead of NoteItemType | NEG-INVALID-ITEMTYPE | FALSE ✓ | TRUE ✓ |

**Why these three:**

- **Orphan entity** — proves the compositional constraint (NoteItem must be part of a Note) is enforceable at the query level before SHACL shapes exist (Sprint 2).
- **Missing project** — proves the project-scoping constraint (every Note must belong to a Project) is enforceable. This is the same violation as CQ-BOUND-001 but demonstrated with a dedicated fixture.
- **Invalid relation** — proves that property range constraints (`hasItemType` must point to a NoteItemType) are enforceable. This goes beyond the CQ-BOUND queries which only checked existence, not type correctness.

## Files Created

- [ontology/examples/negative-orphan-noteitem.trig](../../../../ontology/examples/negative-orphan-noteitem.trig) — 1 orphan NoteItem + 1 valid NoteItem for contrast, in named graph `negative-test/orphan-item/`.
- [ontology/examples/negative-missing-project.trig](../../../../ontology/examples/negative-missing-project.trig) — 1 Note without `belongsToProject`, in named graph `negative-test/missing-project/`.
- [ontology/examples/negative-invalid-itemtype.trig](../../../../ontology/examples/negative-invalid-itemtype.trig) — 1 NoteItem with `hasItemType` pointing to a Person, alongside a valid item for contrast, in named graph `negative-test/invalid-itemtype/`.
- [ontology/competency-questions/negative-queries.rq](../../../../ontology/competency-questions/negative-queries.rq) — 3 ASK queries with comments documenting expected results on clean vs. negative data.

## Testing

- **Validation method:** Python rdflib — load ontology + each fixture, run detection query.
- **Results (clean demo):**
  - NEG-ORPHAN-NOTEITEM: `false` ✓
  - NEG-MISSING-PROJECT: `false` ✓
  - NEG-INVALID-ITEMTYPE: `false` ✓
- **Results (negative fixtures):**
  - NEG-ORPHAN-NOTEITEM: `true` ✓ (1 orphan detected)
  - NEG-MISSING-PROJECT: `true` ✓ (1 missing project detected)
  - NEG-INVALID-ITEMTYPE: `true` ✓ (1 invalid type detected)
- **Checks not run:** Jena `riot --validate` on negative fixtures (the fixtures are deliberately invalid at the application level but are syntactically valid TriG — riot should pass all three).

## Additional Notes

- Each negative fixture uses a separate named graph IRI (`negative-test/*/`) to avoid polluting the clean demo graph IRI. Multiple fixtures can be loaded alongside the clean demo without triple collision.
- The NEG-INVALID-ITEMTYPE detection uses `FILTER NOT EXISTS { ?type a projecta:NoteItemType }` — this depends on the ontology's class assertion that `projecta:requirement` etc. are `a projecta:NoteItemType`. If a new NoteItemType is added to the ontology without the `a projecta:NoteItemType` assertion, it would be falsely flagged.
- These queries are data-quality checks, not SHACL validation. SHACL shapes (Sprint 2) will provide formal closed-world validation with richer error reporting.
