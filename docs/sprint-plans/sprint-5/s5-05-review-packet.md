# Sprint 5 S5-05 Ontology Proposal Review Packet

## Status

`HUMAN_APPROVED` (2026-08-02)

## Semantic Outcome

The approved v0.4 vocabulary adds three proposal classes under the released `Candidate` class:
`EntityCandidate`, `RelationCandidate`, and `EntityLinkCandidate`. It adds
allowlisted-proposal fields for proposed class/label, relation endpoints and
predicate, bounded link target, and a non-truth confidence score. It also adds
model, prompt, and schema version literals on extraction `prov:Activity`.

The change is additive: no existing IRI is changed and no asserted/inferred
data is modified.

## Justification and Questions

The proposal answers the M3 entity, relation, link, provenance, scope, and
review questions in `ontology/competency-questions/llm-extraction.md` while
preserving the candidate/asserted boundary. Existing source/evidence,
lifecycle, project, and PROV-O terms are reused.

## Semantic Commitment Answers

### `EntityCandidate`, `RelationCandidate`, `EntityLinkCandidate`

- Meaning: respectively an unconfirmed typed-entity proposal, a proposed
  allowlisted relation, and a proposed link from a mention to an existing
  same-project entity.
- Required by: CQ-M3-CAND-001, CQ-M3-REL-001, CQ-M3-LINK-001/002,
  CQ-M3-SAFE-001, and review/governance separation.
- Positive examples: a proposed `projecta:Requirement` mention; a proposed
  `projecta:implements` edge; a link to an existing project entity.
- Counterexamples: a human-confirmed `KnowledgeItem`; a cross-project target;
  an unsupported predicate; a prompt-injection instruction.
- Existing reuse: superclass `Candidate`, source evidence, lifecycle, PROV-O,
  and `belongsToProject` are sufficient foundations but cannot identify the
  proposal payloads or validate endpoints independently.
- Classification: candidate knowledge in `/candidates/`, never asserted or
  inferred. Identity is an opaque IRI per extraction outcome; a later replay
  reuses the idempotent outcome, while a new extraction may create a new
  candidate observation.
- Lifecycle: extracted → validated → pending-review → confirmed/rejected;
  confirmation may promote an appropriate domain fact. Candidate content is
  immutable; review history is provenance.
- Scope/provenance: exactly one project, source evidence, generation activity,
  generator, ontology version, and activity configuration metadata. Links and
  relation endpoints must be same-project unless a future governed policy says
  otherwise.

### Proposed properties

`proposedClass`, `relationSource`, `relationTarget`, `proposedPredicate`, and
`linkTarget` are binary identity-bearing relations. Their endpoints are
validated by SHACL and server allowlists; no OWL characteristic beyond
domain/range is asserted. `proposedLabel` and `confidence` are literals:
labels are immutable source-derived proposal text, while confidence is a
normalized decimal in `[0,1]` and explicitly not truth probability.
`modelVersion`, `promptVersion`, and `schemaVersion` are activity metadata
literals used for reproducibility/audit, not domain facts about the candidate.

## Alternatives Considered

1. Keep all rich proposals as opaque application JSON: rejected because graph
   evidence, bounded-link validation, and review queries could not be answered.
2. Overload `Candidate` with untyped literals: rejected because relation/link
   endpoint identity and shape-specific validation would be lost.
3. Add narrowly scoped subclasses and a small set of fields: preferred because
   it is additive, queryable, SHACL-validatable, and keeps untrusted proposals
   distinct from asserted classes.

## Artifact Diff

- Semantic source: `ontology/llm-extraction-v04.ttl`.
- Validation: `ontology/shapes/llm-extraction-draft-shapes.ttl`.
- Positive fixture: `ontology/examples/llm-extraction-v04-draft.trig`.
- Negative fixture: `ontology/examples/shacl-negative-llm-extraction-cross-project.trig`.
- Competency queries: `ontology/competency-questions/llm-extraction-v04-draft-queries.rq`.
- Migration/version: v0.4.0 approved; no migration required.

## Validation Evidence

- `git diff --check`: passed.
- RDF/SHACL validation: approved v0.4 artifacts were validated with the Sprint 5
  ontology evidence and remain additive to the released v0.3 contract.
- Manual/graphify audit: completed against released terms and shapes.

## Compatibility and Risk

The proposal is additive and leaves v0.1–v0.3 data, queries, shapes, graph
routing, and lifecycle APIs unchanged. The main risk is approving durable
metadata or endpoint semantics too broadly; server allowlists and SHACL must
remain stricter than model output. No inference rule, migration, or external
provider dependency is introduced.

## Approval Record

- [x] Semantic meaning approved.
- [x] Vocabulary names and IRIs approved.
- [x] Validation behavior, including same-project endpoint rules, approved.
- [x] No inference rule approved; candidates remain reviewable proposal data.
- [x] No migration required; additive v0.4 release approved.
- [x] Implementation and Sprint 5 release step authorized.
