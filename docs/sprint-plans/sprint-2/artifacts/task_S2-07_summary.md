# Task Summary: S2-07 — Draft the v0.2 Term Inventory

**Sprint:** Sprint 2 — Governed Knowledge Lifecycle
**Task:** S2-07 — Draft the v0.2 Term Inventory

## Summary of Work

Drafted the complete v0.2 ontology term inventory using the `projecta-evolve-ontology` skill workflow. Every term was run through the semantic commitment interview, classified through the competency gate and semantic commitment gate, and evaluated against alternatives.

The inventory defines **21 new terms** (4 classes, 3 object properties, 6 datatype properties, 8 controlled individuals) plus documents the reuse of 10 external vocabulary terms (`prov:Activity`, `prov:wasDerivedFrom`, `prov:wasGeneratedBy`, `prov:wasAssociatedWith`, `prov:used`, `prov:generated`, `prov:generatedAtTime`, `prov:endedAtTime`, `rdf:Statement` with its three components).

**Classes (4):**
- `Candidate` — proposed knowledge in the candidates graph, subclass of `Entity`. Full interview covers identity criterion (IRI, distinct per extraction attempt), independence (compositional to project), lifecycle (Extracted → Validated → PendingReview → Confirmed/Rejected), and necessary conditions (7 mandatory properties).
- `LifecycleStatus` — controlled vocabulary container, subclass of `Entity`. Parallel to v0.1 `NoteItemType`. 8 individuals define the permitted lifecycle states.
- `KnowledgeItem` — superclass for asserted facts, subclass of `Entity`. Carries `validFrom`/`validTo`, supports `supersededBy`, and traces back to candidate via `prov:wasDerivedFrom`.
- `Requirement` — first concrete KnowledgeItem subclass. **Critically distinguished** from the v0.1 `projecta:requirement` (kebab-case NoteItemType individual) — different case, different kind (class vs individual), different graph (asserted vs sources).

**Object Properties (3):**
- `candidateStatus` — Candidate → LifecycleStatus. Current state as convenience denormalization; authoritative history in provenance activities.
- `reviewDecision` — prov:Activity → LifecycleStatus (confirmed/rejected). Explicit property avoids reconstructing the state machine to answer "what did the reviewer decide?"
- `supersededBy` — KnowledgeItem → KnowledgeItem. Replacement link; `owl:inverseOf supersedes`.

**Datatype Properties (6):**
- `rejectionReason`, `retractionReason` — xsd:string, immutable, attached to review/retraction activities.
- `generator`, `proposedOntologyVersion` — xsd:string, immutable, attached to Candidate to record extraction provenance.
- `validFrom`, `validTo` — xsd:date, on KnowledgeItem. Assertion metadata uses `rdf:Statement` per S2-06 decision.

**Controlled Individuals (8 LifecycleStatus values):**
`extracted`, `validated`, `pending-review`, `confirmed`, `rejected`, `asserted`, `superseded`, `retracted` — with permitted transition state machine documented.

Four alternatives were explicitly considered and rejected with rationale: activity subclasses (no CQ requires them), full KnowledgeItem subclass set (only Requirement is exercised by CQs), candidateStatus as string (fragile), and skipping KnowledgeItem superclass (properties would need duplication).

Five unresolved questions are documented with recommendations: candidate dedup, candidate temporal validity, retraction vs supersession distinction, KnowledgeItem content model, and NoteItem identity.

## Files Modified

- [docs/ontology/term-inventory-sprint-2.md](../../../../docs/ontology/term-inventory-sprint-2.md) — New file: complete v0.2 term inventory with semantic commitment interviews for all 21 new terms, external vocabulary reuse documentation, alternatives considered, compatibility analysis, and unresolved questions.

## Testing

- **Test Type:** Specification and semantic review (no automated test — Turtle implementation is S2-09).
- **Validation Performed:**
  - Every term maps to at least one numbered lifecycle competency question (CQ-LC-*, CQ-EV-*, CQ-REV-*, CQ-TEMP-*, CQ-ISO-*, CQ-SCOPE-*).
  - Every term was run through the full semantic commitment interview: generic questions (8), class-specific questions (12), object-property-specific questions (12), or datatype-property-specific questions (6) as applicable.
  - The critical `Requirement` (PascalCase class) vs `requirement` (kebab-case individual) distinction was verified against the v0.1 IRI catalog in the compatibility baseline — these are distinct IRIs with distinct purposes.
  - All terms respect the S2-06 REIF decision — assertion metadata properties (`validFrom`, `validTo`) are designed for dual representation (direct triple + `rdf:Statement` metadata).
  - The external vocabulary reuse list was cross-checked against the standard prefix set in the namespace policy — no new external dependencies are introduced.
  - Compatibility analysis confirms zero regression risk: all v0.1 terms, demo graphs, competency queries, and negative fixtures are untouched.
- **Status:** PENDING_HUMAN_REVIEW (S2-08).

## Additional Notes

- The 21 new terms bring the total v0.2 vocabulary to 20 classes (9 + 4 new + 7 anticipated external), 9 object properties (6 + 3 new), 9 datatype properties (3 + 6 new), and 17 controlled individuals (9 + 8 new). This respects the decision to keep a flat namespace for the v0.x phase.
- `KnowledgeItem` is the most architecturally significant addition — it establishes the asserted-knowledge layer that all future domain classes (Decision, Question, Risk, etc.) will subclass.
- The content model decision (rdfs:label on asserted facts, full text in source) avoids duplicating evidentiary text and keeps the asserted graph focused on governed facts rather than raw content.
- Activity type differentiation by property presence rather than OWL subclasses is a pragmatic v0.2 choice that can be revisited if inference or SHACL shapes need hard typing.
