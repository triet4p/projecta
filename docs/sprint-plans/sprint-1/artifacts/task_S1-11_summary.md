# Task Summary: S1-11 — Implement Competency Queries

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-11 — Implement Competency Queries

## Summary of Work

Implemented all 14 competency questions from S1-02 as executable SPARQL queries and validated them against the Sprint 1 ontology kernel (core.ttl + communication.ttl) and demo graph (quick-note-demo.trig). Every query returns the expected result shape and row count.

**Query breakdown by category and result:**

| ID | Type | Rows | Result |
|---|---|---|---|
| CQ-NOTE-001 | SELECT | 1 | Sprint review note listed |
| CQ-NOTE-002 | SELECT | 1 | Author = Le |
| CQ-NOTE-003 | SELECT | 1 | Timestamp = 2026-07-28T10:30:00Z |
| CQ-NOTE-004 | SELECT | 1 | Project = Ecommerce Checkout Redesign |
| CQ-NOTEITEM-001 | SELECT | 6 | All 6 items with types |
| CQ-NOTEITEM-002 | SELECT | 1 | Filtered: Risk item only |
| CQ-NOTEITEM-003 | SELECT | 1 | Requirement content text |
| CQ-PROV-001 | SELECT | 1 | Le's note in project |
| CQ-PROV-002 | SELECT | 1 | Full provenance chain |
| CQ-PROV-003 | SELECT | 6 | All 6 items by Le |
| CQ-COUNT-001 | SELECT + GROUP BY | 6 | Count=1 per type |
| CQ-COUNT-002 | SELECT + COUNT | 1 | Count=1 note |
| CQ-BOUND-001 | ASK | false | No orphan notes ✓ |
| CQ-BOUND-002 | ASK | false | No orphan items ✓ |

All queries use parameterized `VALUES` clauses for instance IRIs, making them reusable against any project/person/note data conforming to the vocabulary.

## Files Modified

- [ontology/competency-questions/quick-note-queries.rq](../../../../ontology/competency-questions/quick-note-queries.rq) — New file: 14 SPARQL queries with CQ identifiers, Vietnamese questions, answer shapes, and expected results.
- [scripts/validate_ontology.py](../../../../scripts/validate_ontology.py) —
  Current consolidated validator. The original query-only prototype was merged
  into the Docker-native Sprint 1 suite during S1-14A.

## Testing

- **Current validation command:**
  `docker compose run --build --rm ontology-test`
- **Data loaded:** 152 triples (43 core + 76 communication + 33 demo)
- **Result:** 14/14 queries passed
  - 12 SELECT queries: all return >= 1 row with correct variable bindings
  - 2 ASK queries: both return `false` (no orphans — correct for clean demo data)
- **Query types covered:** Basic SELECT, SELECT with multi-variable VALUES, SELECT with GROUP BY/COUNT, SELECT with FILTER NOT EXISTS, ASK with FILTER NOT EXISTS
- **Checks not run:** Jena `sparql` CLI (Jena not installed — deferred to S1-12)

## Additional Notes

- **TriG loading in rdflib:** Discovered that `Graph.parse()` on TriG silently ignores named-graph content. The validation script uses `Dataset.parse()` + manual merge to make all triples queryable. The S1-12 Jena runner will need a similar strategy or proper named-graph `FROM` clauses in queries.
- **Console encoding:** Vietnamese text in query results triggers `charmap` errors on Windows terminals. The validation script handles this with ASCII-safe fallback in preview output. Actual SPARQL results are correct (verified via row counts and IRI-only columns).
- **Query design pattern:** All queries use `VALUES` clauses for parameterized IRIs rather than hardcoding them in triple patterns. This makes the queries reusable against any dataset conforming to the vocabulary — only the `VALUES` blocks need adjustment.
- **Bridge to S1-12:** The query-only prototype was consolidated into
  `validate_ontology.py`, which runs in the pinned Jena image and preserves the
  rdflib Dataset strategy for TriG named graphs.
