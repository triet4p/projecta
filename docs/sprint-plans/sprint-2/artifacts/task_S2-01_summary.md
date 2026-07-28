# Task Summary: S2-01 — Fix the Lifecycle Slice Boundary

**Sprint:** Sprint 2 — Governed Knowledge Lifecycle
**Task:** S2-01 — Fix the Lifecycle Slice Boundary

## Summary of Work

Defined the precise boundary of the Knowledge Lifecycle use case as the foundation for Sprint 2's ontology v0.2 work. The document specifies the standard use case with actors (BrSE, Project Coordinator, Technical BA, Tech Lead), trigger (an existing Sprint 1 `NoteItem` in the sources graph), preconditions (complete source provenance, named graphs, project membership), main flow (six steps from source identification through assertion promotion), and postconditions (graph-isolated entities with full provenance across all five named graphs). It includes a concrete positive example — a step-by-step walkthrough tracing the "address confirmation" Requirement NoteItem from the Sprint 1 Ecommerce Checkout Redesign scenario through candidate extraction (with Turtle examples), SHACL validation, human review confirmation by BrSE Le, and assertion promotion. Five counterexamples clarify invalid lifecycle patterns: direct assertion without candidate stage, candidate masquerading as asserted fact, status mutation without provenance activity, cross-project assertion without authorization, and overwriting historical state. Ten non-goals are explicitly listed with rationale and target sprint assignments. The document also identifies the ontology requirements derived from this use case: lifecycle classes (Candidate, LifecycleStatus), PROV-O properties, Projecta-specific lifecycle properties, named-graph templates, and SHACL shapes.

## Files Modified

- [docs/use-cases/knowledge-lifecycle.md](../../../../docs/use-cases/knowledge-lifecycle.md) — New file: authoritative Knowledge Lifecycle use case definition with positive example, counterexamples, non-goals, and ontology requirements.

## Testing

- **Test Type:** Documentation review (no automated test — this is a specification artifact).
- **Validation Performed:**
  - Cross-referenced against [Quick Note use case](../../../../docs/use-cases/quick-note.md) — the positive example continues the Sprint 1 "Ecommerce Checkout Redesign" scenario with the same NoteItem, actors, and project.
  - Cross-referenced against [Ontology Design §8-9](../../../../docs/initialization/05-Ontology-Design.md) — the lifecycle state machine (Extracted → Validated → PendingReview → Confirmed/Rejected → Asserted → Superseded/Retracted) and named-graph model are faithfully represented.
  - Cross-referenced against [Project Overview §5.2](../../../../docs/initialization/01-Project-Overview.md) — evidence-grounded intelligence: every asserted fact traces back to a source NoteItem.
  - Cross-referenced against carried Sprint 2 decisions: PROV-O reuse (no custom provenance vocabulary), five separate named graphs, no overwrite of historical data, single-project scope, no RDF-star before benchmark.
  - Verified all v0.1 IRIs are preserved and no renaming or repurposing occurs — Candidate, LifecycleStatus, and lifecycle properties are purely additive.
  - Verified the counterexamples address the five main lifecycle boundary risks: skipping candidate stage, graph isolation violation, silent status mutation, unauthorized cross-project assertion, and historical data destruction.
- **Status:** Awaiting human review (see acceptance criteria in the document).

## Additional Notes

- This is a pure documentation task. The acceptance criteria include a human review gate — the use case boundary must be confirmed before S2-03 (competency question review) proceeds.
- The positive example's Turtle fragments are illustrative and use compact URIs. The formal TriG fixture will be created in S2-10 (named-graph contract) and S2-15 (competency tests).
- The non-goals table explicitly defers LLM extraction (S3+), review UI (S3+), Semantic Core API (S3), inference execution (S2-17 scope analysis only), and connector integration (S3+) — keeping Sprint 2 focused on semantic contracts and validation.
- The provenance vocabulary reuses PROV-O exclusively (`prov:Activity`, `prov:wasDerivedFrom`, `prov:wasGeneratedBy`, `prov:wasAssociatedWith`, `prov:used`, `prov:generated`, `prov:generatedAtTime`, `prov:endedAtTime`) — Projecta-specific properties are limited to lifecycle semantics not covered by PROV-O (`candidateStatus`, `reviewDecision`, `rejectionReason`, `retractionReason`, `hasSourceEvidence`, `proposedOntologyVersion`, `generator`, `validFrom`, `validTo`, `supersededBy`).
