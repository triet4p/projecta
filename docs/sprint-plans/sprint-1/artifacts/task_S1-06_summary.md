# Task Summary: S1-06 — Draft the Term Inventory

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-06 — Draft the Term Inventory

## Summary of Work

Conducted the full semantic commitment interview for every class and property needed by the Sprint 1 Quick Note vertical slice. Produced a 20-term inventory with detailed answers to all mandatory questions from the `projecta-evolve-ontology` skill's semantic commitment interview.

The inventory covers:

- **9 classes:** Entity, Context, Project, Actor, Person, SourceArtifact, Note, NoteItem, NoteItemType
- **4 object properties:** belongsToProject, hasNoteItem, authoredBy, hasItemType
- **3 datatype properties:** name, contentText, recordedAt
- **9 controlled individuals:** Requirement, Decision, Question, Task, Risk, Assumption, Constraint, ProgressUpdate, ResearchNeed (all instances of NoteItemType)

Every term is mapped to specific competency questions from S1-02. Each class interview covers identity criterion, independence, lifecycle/membership change, superclass, and the "is this actually a class/role/state/relation" gate. Object property interviews cover arity, temporal needs, inverse, characteristics, cardinalities, and cross-project behavior. Datatype property interviews cover literal-vs-resource justification, datatype precision, mutability, and cardinalities.

Four alternatives were evaluated and rejected: NoteItemType as subclasses (individuals preferred), contentText as a ContentNode resource (over-engineered), skipping abstract superclasses (would create migration debt), and reusing dcterms:title (too narrow).

## Files Modified

- [docs/ontology/term-inventory-sprint-1.md](../../../../docs/ontology/term-inventory-sprint-1.md) — New file: 20-term inventory with full semantic commitment interview answers, alternatives considered, compatibility impact matrix, unresolved questions, and human review checkboxes.

## Testing

- **Test Type:** Semantic proposal review (no automated test — implementation is S1-08).
- **Validation Performed:**
  - Every term is linked to at least one competency question from S1-02.
  - Class hierarchy is consistent with Ontology Design §4.
  - Property naming follows the approved namespace policy (S1-04/S1-05).
  - Object properties that align with PROV-O (`authoredBy` → `prov:wasAttributedTo`) are identified with explicit resolution questions for the human reviewer.
  - Compatibility impact matrix reports "no impact" for all consumers (greenfield).
  - Two unresolved questions are explicitly raised for human decision.
- **Status:** PROPOSAL_ONLY — awaiting S1-07 human review.

## Additional Notes

- The `NoteItemType` class + 9 controlled individuals pattern was chosen over subclassing to keep the class hierarchy stable when types are added — new types are new individuals, not new classes.
- `authoredBy` as a subproperty of `prov:wasAttributedTo` is recommended but flagged as an unresolved question because it requires PROV-O import and the human reviewer should confirm the alignment.
- Abstract superclasses (Entity, Context, Actor, SourceArtifact) are included in Sprint 1 despite no direct CQ usage because: (1) they are established in Ontology Design §4, (2) removing them now creates migration debt when Sprint 2 adds KnowledgeItem subclasses, and (3) the cost is 4 class declarations with rdfs:subClassOf.
