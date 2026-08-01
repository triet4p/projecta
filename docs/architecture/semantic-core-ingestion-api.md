# Semantic Core Quick Note Ingestion Contract — Sprint 4 M2

**Status:** HUMAN_APPROVED
**Task:** S4-07

## Purpose and Caller Boundary

This private, domain-safe Semantic Core operation is used by FastAPI for atomic
Quick Note capture. It extends the existing candidate validation, confirmation,
rejection, and read contract; it is not a public Fuseki or SPARQL interface.

Only the trusted Application API may call `POST /v1/quick-notes/captures` over
the internal service network. Trusted project, actor, and request IDs use the
private context mechanism, never the JSON body. The endpoint rejects graph
IRIs, arbitrary RDF, SPARQL, ontology versions, author IRIs, candidate IDs,
and asserted IDs supplied by callers.

## Canonical Operation

The operation needs trusted project ID, actor ID, request ID, and an
`Idempotency-Key`; its body is:

```json
{
  "rawText": "Confirm address before payment. Tax API timeout is 15%.",
  "segments": [
    {
      "type": "requirement",
      "startOffset": 0,
      "endOffset": 31,
      "text": "Confirm address before payment."
    }
  ]
}
```

The Core independently verifies LF normalization, ordered non-overlapping
half-open Unicode-code-point ranges, substring equality, and the nine released
`NoteItemType` values. It derives all opaque resource IDs and graph IRIs.

## Atomic Transaction Contract

For a first successful request, one transaction must:

1. Create one `Note` in the trusted project sources graph with canonical raw
   text, author, project, and recorded time.
2. Create one `NoteItem` per segment in sources, linked to that Note with its
   type, copied text, and approved start/end evidence offsets.
3. Create one `Candidate` per NoteItem in candidates, with source link,
   generator identifier, proposed ontology version, generated time, project,
   and `extracted` status.
4. Append one extraction `prov:Activity` per candidate in provenance, bound to
   project, actor/tool, source item, and generated candidate.
5. Persist a durable, private idempotency outcome in the same effective
   transaction boundary.

It must not write asserted or inferred facts. Source records and candidate
content are immutable after capture; review appends lifecycle history rather
than rewriting source evidence. Any input, shape, graph route, or storage
failure rolls back all five effects.

## Idempotency

The uniqueness scope is:

```text
trusted project + capture endpoint + Idempotency-Key
```

The Core canonicalizes the body and stores its fingerprint with the finalized
opaque response. The same key and fingerprint return that result as a replay;
a changed fingerprint returns `409 IDEMPOTENCY_KEY_REUSED` without mutation.
The record is private operational metadata, not an asserted fact or public
evidence-read resource.

## Response and Failures

The first response is `201`; replay is `200`:

```json
{
  "note": {"id": "note-01", "recordedAt": "2026-07-31T10:00:00Z"},
  "candidates": [
    {"id": "cand-01", "sourceItemId": "item-01", "status": "extracted"}
  ]
}
```

Malformed input maps to `INVALID_REQUEST`, a reused key to
`IDEMPOTENCY_KEY_REUSED`, missing released artifacts/store to a retryable
service failure, and transactional failure to a sanitized internal failure.
The Application API owns public `application/problem+json` translation.

## Compatibility and Tests

The operation reuses the named-graph contract, `Note`, `NoteItem`,
`Candidate`, PROV-O, lifecycle status, and review/read operations. It depends
on the implemented local raw-text/evidence-offset extension, which remains
pending separate ontology release approval.

S4-14/S4-19 must prove graph separation, rollback after injected failure,
duplicate replay prevention, malformed-span rejection before mutation,
cross-project isolation, and no inferred facts. The existing 73 ontology
checks remain mandatory. No inference rule, automatic classification, entity
linking, note mutation, bulk ingestion, arbitrary candidate typing, or direct
Fuseki endpoint is added.
