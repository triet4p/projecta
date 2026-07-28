# Task Summary: S1-08 — Implement Core Vocabulary

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-08 — Implement Core Vocabulary

## Summary of Work

Implemented the approved 20-term inventory as two Turtle modules, following the namespace policy (S1-04/S1-05) and semantic commitments (S1-06/S1-07). All 20 terms from the inventory are present; no extra terms were added.

**Core module** ([ontology/core.ttl](../../../../ontology/core.ttl)) — 6 classes, 1 object property, 1 datatype property:
- Entity (root), Context → Project, Actor → Person, SourceArtifact
- `belongsToProject` (Entity → Project)
- `name` (Entity → xsd:string)
- Ontology metadata: version IRI `v/0.1/`, versionInfo `0.1.0`, creation date, creator

**Communication module** ([ontology/communication.ttl](../../../../ontology/communication.ttl)) — 3 classes, 5 object properties (3 primary + 2 inverses), 2 datatype properties, 9 controlled individuals:
- Note (subClassOf SourceArtifact), NoteItem (subClassOf Entity), NoteItemType (subClassOf Entity)
- `hasNoteItem` ↔ `isItemOf` (Note → NoteItem, with inverse)
- `authoredBy` ↔ `authorOf` (SourceArtifact → Person, subPropertyOf `prov:wasAttributedTo`, with inverse)
- `hasItemType` (NoteItem → NoteItemType)
- `contentText` (NoteItem → xsd:string), `recordedAt` (SourceArtifact → xsd:dateTime)
- 9 NoteItemType individuals: Requirement, Decision, Question, Task, Risk, Assumption, Constraint, ProgressUpdate, ResearchNeed

## Files Modified

- [ontology/core.ttl](../../../../ontology/core.ttl) — New file: 39 triples. Foundation classes and shared properties.
- [ontology/communication.ttl](../../../../ontology/communication.ttl) — New file: 74 triples. Quick Note vocabulary, properties, inverses, and controlled individuals.

## Testing

- **Test Tool:** Python `rdflib` 7.x (graph.parse with format='turtle')
- **Parse result:** Both files parse without errors.
- **Triple counts verified:**
  - 9 classes (Entity, Context, Project, Actor, Person, SourceArtifact, Note, NoteItem, NoteItemType)
  - 6 object properties (belongsToProject, hasNoteItem, isItemOf, authoredBy, authorOf, hasItemType)
  - 3 datatype properties (name, contentText, recordedAt)
  - 9 controlled individuals (Requirement, Decision, Question, Task, Risk, Assumption, Constraint, ProgressUpdate, ResearchNeed)
  - 1 ontology declaration with version metadata
- **Execution command:** `uv run --with rdflib python -c "g = rdflib.Graph(); g.parse('ontology/core.ttl', format='turtle'); g.parse('ontology/communication.ttl', format='turtle')"`
- **Checks not run:** Jena `riot` parsing (Jena CLI not installed yet — deferred to S1-12); OWL consistency checks (no reasoner configured).

## Additional Notes

- `owl:imports` in communication.ttl references `<https://w3id.org/projecta/ontology/v/0.1/core>` — this is a semantic declaration. For offline Jena testing in S1-12, a `LocationMapper` or manual load order (core before communication) will be used.
- Inverse properties (`isItemOf`, `authorOf`) are declared as `owl:inverseOf` rather than omitted — they serve competency questions CQ-PROV-002 and CQ-PROV-003 directly.
- PROV-O alignment: `authoredBy rdfs:subPropertyOf prov:wasAttributedTo` per the approved S1-07 decision. Full PROV-O import is deferred; the `prov:` prefix is declared and the subproperty assertion is valid RDF.
- No SHACL shapes, no rules, no instance data — these are the next tasks (S1-09, S1-10, S1-11).
