# Quick Note M2 v0.2 Reuse and Gap Matrix

**Status:** HUMAN_APPROVED
**Task:** S4-03 — Audit the released semantic contract
**Released baseline inspected:** ontology v0.2.0 and its 73-check suite

## Result

The released contract is sufficient for project-scoped source capture,
candidate lifecycle, review, asserted result, graph isolation, and provenance
traversal. It is not sufficient for exact character-range evidence. This is a
mandatory M2 gap because the executable boundary requires each typed segment to
be provably equal to a range of the submitted raw note.

| M2 field / CQ | Released reuse | Shape / query evidence | Result |
|---|---|---|---|
| Project scope | `projecta:belongsToProject` | `NoteShape`, `CandidateShape`, CQ-SCOPE-001/002 | Reuse |
| Raw source item text | `projecta:contentText` on `NoteItem` | `NoteItemShape`, CQ-NOTEITEM-001/003, CQ-EV-001 | Reuse for segment text only |
| Note author and capture time | `projecta:authoredBy`, `projecta:recordedAt` | `NoteShape`, CQ-NOTE-002/003, CQ-PROV-002 | Reuse |
| Segment parent and type | `projecta:isItemOf` / `hasNoteItem`, `projecta:hasItemType` | `NoteItemShape`, CQ-NOTEITEM-001 | Reuse |
| Candidate source evidence | `prov:wasDerivedFrom`, `prov:wasGeneratedBy`, `prov:generatedAtTime`, `projecta:generator`, `projecta:proposedOntologyVersion` | `CandidateShape`, CQ-EV-001/003 | Reuse |
| Candidate review state | `projecta:candidateStatus`, `projecta:reviewDecision`, `projecta:rejectionReason` | `CandidateShape`, `CandidateRejectionShape`, CQ-LC-001/003, CQ-REV-001 | Reuse |
| Asserted result and provenance | `projecta:KnowledgeItem`, `projecta:Requirement`, `prov:wasDerivedFrom`, `prov:wasAttributedTo`, RDF reification | temporal/isolation shapes; CQ-EV-002, CQ-TEMP-001 | Reuse for released mapped types |
| Graph separation and project isolation | five graph contract and isolation shapes | CQ-ISO-001/002, CQ-SCOPE-001/002 | Reuse |
| Exact note raw text | No released property for the Note body | `NoteShape` requires `name`, author, project, time; no raw-body path | Gap |
| Exact source span offsets | No released start/end offset properties or span constraint | `NoteItemShape` validates text/type/parent only | Gap |
| Offset normalization and equality | No ontology term, shape, or query | No released validation for range, overlap, or substring equality | Gap; application rule plus ontology support required |
| Capture idempotency key/fingerprint | No ontology term | Semantic Core contract §6 classifies it as operational state | Reuse boundary: keep outside ontology |
| Inference output | Reserved inferred graph only | named-graph contract §3.4 | Deferred; not an M2 criterion |

## Audit Method and Compatibility

The audit read the released ontology modules, source/candidate/temporal and
isolation shapes, named-graph contract, lifecycle and Quick Note queries, the
Semantic Core API contract, and the validation runner. No released IRI is
changed by this task.

The two gaps are coupled: offsets cannot establish evidence equality unless the
canonical note body is also represented. Adding only offsets would produce
unverifiable numbers; adding only a raw body would not identify the selected
span. The smallest coherent resolution is therefore a governed proposal for a
Note body plus a NoteItem half-open offset pair and SHACL/application checks.

## No-Gap Findings

No vocabulary, shape, or rule change is needed for candidate status, review
decision, rejection reason, assertion provenance, graph routing, project
isolation, or inference deferral. No inference rule is proposed.

## Required Human Decision

Review the linked S4-04 proposal before implementation. Until it is approved,
the Sprint 4 boundary is specified but cannot be implemented without violating
the released semantic contract.
