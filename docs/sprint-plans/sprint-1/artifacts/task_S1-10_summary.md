# Task Summary: S1-10 — Build the Demo Graph

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-10 — Build the Demo Graph

## Summary of Work

Created a TriG fixture from the Quick Note positive example ([docs/use-cases/quick-note.md](../../../../docs/use-cases/quick-note.md) §3). The demo graph instantiates the complete "Ecommerce Checkout Redesign" scenario: BrSE Le captures 6 typed note items (Requirement, Risk, Decision, Task, Question, Assumption) during a sprint review meeting.

**Single named graph:** `https://w3id.org/projecta/data/project/ecommerce-checkout/`

Instance IRIs follow the namespace policy pattern: `/project/{project-id}/{entity-type}/{local-id}`

| Instance | IRI | Triples |
|---|---|---|
| Project | `.../project/ecommerce-checkout` | 2 |
| Person (Le) | `.../person/le` | 2 |
| Note | `.../note/sprint-review-2026-07-28` | 5 |
| 6 × NoteItem | `.../note-item/ni-1` through `ni-6` | 24 (4 each) |
| **Total** | **9 instances** | **33** |

Each NoteItem carries: `a projecta:NoteItem`, `isItemOf` (parent note), `hasItemType` (controlled vocabulary individual), `contentText` (exact Vietnamese text from the use case).

## Files Modified

- [ontology/examples/quick-note-demo.trig](../../../../ontology/examples/quick-note-demo.trig) — New file: 33 triples in 1 named graph. Positive example fixture for competency query testing (S1-11) and Jena regression (S1-12).

## Testing

- **Parse result:** TriG syntax OK (rdflib). Graph parses without errors.
- **Instance counts verified:**
  - 1 Project ✓
  - 1 Person ✓
  - 1 Note ✓
  - 6 NoteItems ✓
- **Data integrity verified:**
  - Note.author = Person Le ✓
  - Note.project = "Ecommerce Checkout Redesign" ✓
  - Note.recordedAt = 2026-07-28T10:30:00Z ✓
  - All 6 NoteItems connected to parent Note (zero orphans) ✓
  - All 6 item types present: Requirement, Risk, Decision, Task, Question, Assumption ✓
- **Execution command:** `uv run --with rdflib python -c "g = rdflib.Dataset(); g.parse('ontology/examples/quick-note-demo.trig', format='trig')"`
- **Checks not run:** Jena TriG parsing (Jena CLI not installed — deferred to S1-12).

## Additional Notes

- **Compact URI limitation discovered:** Turtle/TriG prefixed names (compact URIs) cannot contain `/`. The original design tried `proj-data:project/ecommerce-checkout` which is syntactically invalid. Full IRIs were used instead — they're verbose but correct. SPARQL queries in S1-11 can use `BIND` or `VALUES` clauses to shorten repeated IRI references.
- **Single named graph for Sprint 1:** The source/asserted/inferred graph separation from Ontology Design §8 is deferred to Sprint 2. For the demo graph, all 9 instances co-exist in one graph. The competency queries (S1-11) will query this single graph.
- **Vietnamese text preserved:** All NoteItem `contentText` values contain the exact diacritical Vietnamese text from the use case. rdflib handles UTF-8 string literals correctly.
- **`hasItemType` cross-references:** NoteItems reference ontology-namespace controlled individuals (e.g., `projecta:requirement`), demonstrating the vocabulary/data separation from the namespace policy.
