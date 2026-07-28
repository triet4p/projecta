# Task Summary: S2-04 — Freeze the v0.1 Compatibility Baseline

**Sprint:** Sprint 2 — Governed Knowledge Lifecycle
**Task:** S2-04 — Freeze the v0.1 Compatibility Baseline

## Summary of Work

Froze the complete v0.1 ontology surface as the compatibility contract that v0.2 must not break. The baseline document catalogs every released v0.1 IRI (9 classes, 6 object properties, 3 datatype properties, 9 controlled individuals, and inverse properties), documents the 6 external vocabulary dependencies (rdf, rdfs, owl, xsd, prov, dcterms), enumerates all 32 Sprint 1 validation checks with their expected results organized by category (6 syntax, 4 vocabulary count, 1 query inventory, 12 SELECT, 2 ASK, 1 negative inventory, 6 negative fixture), and defines the graph/query behavior contract for the demo graph, competency queries, and negative fixtures.

Classified v0.2 as an ADDITIVE (MINOR) release per the namespace policy, with explicit lists of permitted additive changes (new classes, properties, controlled individuals, ontology modules, named graphs, SHACL shapes, competency questions) and forbidden breaking changes (no renaming, domain/range changes, deletions, hierarchy changes, demo graph mutations that alter CQ results, or mandatory property additions to v0.1 classes). Identified four gray-area changes with recommendations (adding superclasses to v0.1 classes, adding superproperties, broadening property domains, and adding inverse declarations).

Defined the regression test contract with the single canonical invocation (`docker compose run --build --rm ontology-test`), specifying what must pass (v0.1 syntax, v0.2 syntax, v0.1 vocabulary counts, all CQ results, negative fixtures, SHACL validation) and what constitutes a regression failure.

## Files Modified

- [docs/ontology/v0.1-compatibility-baseline.md](../../../../docs/ontology/v0.1-compatibility-baseline.md) — New file: complete v0.1 IRI catalog, 32-check inventory, v0.2 additive/breaking classification, gray-area analysis, and regression test contract.

## Testing

- **Test Type:** Documentation and analysis (no new automated test — this is a specification and classification artifact).
- **Validation Performed:**
  - Cross-referenced the IRI catalog against [core.ttl](../../../../ontology/core.ttl) and [communication.ttl](../../../../ontology/communication.ttl) — every term listed exists in the Turtle files with the stated superclass, domain, range, and module.
  - Cross-referenced the 32-check inventory against [validate_ontology.py](../../../../scripts/validate_ontology.py) — every check name matches a `Check` object created in `validate_syntax()`, `validate_vocabulary()`, `validate_competency_queries()`, or `validate_negative_fixtures()`. Total count verified: 6 + 4 + 1 + 12 + 2 + 1 + 6 = 32.
  - Cross-referenced the additive/breaking classification against the [namespace policy](../../../../docs/ontology/namespace-policy.md) §5 — MINOR = additive changes that don't invalidate existing data.
  - Verified the 9 controlled individuals match the approved kebab-case IRIs from the [2026-07-28] decision.
  - Verified the gray-area recommendations are consistent with the carried Sprint 2 decisions (no v0.1 IRI changes, PROV-O reuse, named-graph separation).
- **Status:** Awaiting human review.

## Additional Notes

- The 32-check inventory uses stable identifiers (SYN-01…06, VOC-01…04, CQI-01, CQ-01…14, NQI-01, NEG-01a…03b) for traceability. These can be used in CI failure messages to pinpoint exactly which check regressed.
- The vocabulary count checks (VOC-01 through VOC-03) will naturally change when v0.2 adds new terms — the baseline documents this as an expected additive change, not a regression. VOC-04 (9 NoteItemType individuals) must remain exactly 9.
- The "gray areas" section is actionable: if any gray-area change is needed during S2-07–S2-09, it should be called out explicitly so the human reviewer can approve or escalate it.
