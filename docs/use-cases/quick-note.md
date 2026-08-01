# Quick Note Use Case — M2 Executable Boundary

**Status:** HUMAN_APPROVED

## Purpose

This is the Sprint 4 executable boundary for manual Quick Note capture. It
supersedes the Sprint 1 delivery boundary while preserving its released source
semantics. It defines the input that the application may accept and the graph
effects that the Semantic Core must produce; it is not an API implementation.

## Actors and Preconditions

The capture actor is a BrSE, Project Coordinator, or Technical Business
Analyst. Trusted middleware supplies a project ID, actor ID, and request ID;
none comes from the request body. The actor is authorized for that project.

The caller submits one non-empty Unicode raw note and an ordered, non-empty
list of typed segments. Every segment has one released `NoteItemType`, a
half-open evidence range `[startOffset, endOffset)`, and text exactly equal to
the indicated raw-note substring. Offsets count Unicode code points, not UTF-8
bytes or UTF-16 code units. Segments may be adjacent or disjoint; overlapping
segments are rejected for M2.

## Canonical Capture Request

```json
{
  "rawText": "Confirm address before payment. Tax API timeout is 15%.",
  "segments": [
    {
      "type": "requirement",
      "startOffset": 0,
      "endOffset": 31,
      "text": "Confirm address before payment."
    },
    {
      "type": "risk",
      "startOffset": 32,
      "endOffset": 55,
      "text": "Tax API timeout is 15%."
    }
  ]
}
```

The application canonicalizes line endings to `\n` before calculating offsets,
preserves all other characters, and sends the canonical request plus trusted
context to the Semantic Core. The server creates opaque note, note-item, and
candidate IDs. Clients cannot select RDF IRIs, graph IRIs, SPARQL, candidate
IDs, reviewer IDs, or asserted-item IDs.

## Main Flow and Graph Diff

1. The application validates the canonical request before requesting any
   semantic mutation.
2. The Semantic Core routes the request only from trusted project context and
   atomically creates the source Note and one source NoteItem per segment in
   `/sources/`.
3. It atomically creates one deterministic Candidate per valid NoteItem in
   `/candidates/`, with released lifecycle, generator, ontology-version, and
   source provenance fields.
4. It appends extraction provenance activities in `/provenance/`. The asserted
   and inferred graphs are unchanged.
5. The response returns opaque IDs, canonical offsets, candidate status, and
   the request ID.

The required graph-level result is:

| Graph | Required M2 effect |
|---|---|
| sources | One `Note` and one typed `NoteItem` per valid segment; raw source remains immutable. |
| candidates | One `Candidate` per source NoteItem, derived from that item and marked `extracted`. |
| provenance | Extraction activity and links needed to traverse candidate → NoteItem → Note → author. |
| asserted | No write during capture. |
| inferred | No write during capture; inference is not an M2 acceptance criterion. |

## Deterministic Mapping

Mapping is limited to the released controlled values: `requirement`,
`decision`, `question`, `task`, `risk`, `assumption`, `constraint`,
`progress-update`, and `research-need`. A segment maps only to the candidate
representation supported by the released v0.2 contract. It performs no LLM
extraction, automatic classification, entity linking, confidence scoring, or
fact assertion.

## Idempotency and Atomicity

Capture has a required opaque idempotency key scoped to trusted project and the
canonical request fingerprint. The first successful capture creates the graph
effects above. A replay with the same scope, key, and canonical body returns
the original result and writes no duplicate source, candidate, or provenance
records. Reusing a key with different canonical content fails with a conflict.

If source validation, candidate validation, graph routing, or storage fails,
the operation fails as a whole: no partial source, candidate, or provenance
write may remain. Idempotency bookkeeping is operational state, not RDF domain
truth.

## Failure Cases

| Condition | Required outcome |
|---|---|
| Missing or invalid trusted context | Reject before payload processing; reveal no project data. |
| Empty raw text or no segments | Reject with a request-validation error; no mutation. |
| Unknown, missing, or repeated segment type | Reject; no mutation. |
| Offset outside the canonical raw text, `startOffset >= endOffset`, mismatch between span and text, or overlap | Reject; no mutation. |
| Segment violates released source/candidate validation | Reject; no mutation. |
| Idempotency key reused with different request | Conflict; no mutation. |
| Semantic-store failure | Service failure; transaction rollback; no graph detail or stack trace. |

## Review and Read Boundary

Candidate validation and confirm/reject continue through the released Semantic
Core lifecycle. Confirmation can create an asserted `KnowledgeItem`; rejection
cannot. Read flows may return candidate history, current asserted items, and
the evidence/provenance chain only within trusted project scope.

## Acceptance Scenario

Given trusted context for project `ecommerce-checkout`, Le captures the two
segments in the canonical request. The system returns one note and two
candidates. The sources graph holds the note and exact typed source items; the
candidates graph holds two `extracted` candidates, each derived from its own
item; the provenance graph records both extraction paths. Confirming the
requirement candidate creates one asserted item traceable through its candidate
to the original source span. Rejecting the risk candidate creates no asserted
item. Replaying the capture returns the original IDs, and the inferred graph
remains empty throughout.

## Explicit Non-Goals

- Note edit, delete, versioning, and bulk capture.
- Transcript ingestion, connector-originated capture, UI behavior, and
  authentication-provider implementation.
- LLM extraction, automatic type assignment, entity linking, confidence, or
  auto-assertion.
- Materialized inference rules or inferred facts.
- Client-provided RDF/SPARQL/graph routing or cross-project capture.

## Open Governance Gate

The evidence-offset extension is implemented as a local v0.3 draft and is
covered by the M2 query, positive, negative, and runtime validation evidence.
It still requires separate human release approval before publication.
