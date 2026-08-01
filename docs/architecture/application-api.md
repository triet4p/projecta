# Application API Contract — Sprint 4 M2

**Status:** HUMAN_APPROVED
**Task:** S4-06

## Boundary

FastAPI is the public application boundary for Manual Quick Note. It accepts
typed JSON and trusted request context, validates requests with Pydantic, and
calls only finite Semantic Core operations. It never accepts or creates RDF
IRIs, graph IRIs, RDF, or SPARQL, and it never calls Fuseki.

All paths are relative to `/v1`, use UTF-8 JSON, and return an `X-Request-Id`.
Timestamps are RFC 3339 UTC instants. IDs are opaque URL-safe strings.

## Trusted Context

An authenticated deployment adapter strips client-supplied trusted-context
headers and establishes this context before FastAPI route handling:

```text
projectId: opaque project identifier
actorId: authenticated actor identifier
requestId: correlation identifier
```

FastAPI exposes it only through an internal `TrustedRequestContext` dependency.
It forwards it to Semantic Core over a private service boundary; it never
accepts it in a body, public path, or ordinary client header. Missing or
malformed context returns `401 PROJECT_CONTEXT_REQUIRED` before processing.

## Shared Models and Errors

Every success includes `requestId`. Errors use `application/problem+json`.

| Code | HTTP | Meaning |
|---|---:|---|
| `PROJECT_CONTEXT_REQUIRED` | 401 | Trusted project, actor, or request context is absent or invalid. |
| `INVALID_REQUEST` | 400 | Body, offset, type, header, or query value is invalid. |
| `RESOURCE_NOT_FOUND` | 404 | An opaque resource is not visible in the trusted project. |
| `CANDIDATE_INVALID` | 422 | A candidate fails released or approved-draft semantic validation. |
| `INVALID_LIFECYCLE_STATE` | 409 | The requested decision cannot occur from the current state. |
| `DECISION_CONFLICT` | 409 | A different terminal decision already committed. |
| `IDEMPOTENCY_KEY_REUSED` | 409 | A key is reused with a different canonical operation/body. |
| `SEMANTIC_CONTRACT_UNAVAILABLE` | 503 | Required Semantic Core or semantic artifacts are unavailable. |
| `INTERNAL_ERROR` | 500 | Unexpected failure; no internal detail or partial capture is exposed. |

Downstream failures map to these public codes. Responses never leak Fuseki
addresses, graph names, SPARQL, stack traces, or other-project identifiers.

## Capture Endpoint

`POST /quick-notes` requires `Idempotency-Key` (1–128 opaque ASCII characters).

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

Pydantic rejects empty raw text or segments, unknown item types, non-integer
offsets, ranges outside normalized raw text, start >= end, overlap, and text
that differs from the indicated Unicode-code-point substring. It normalizes
CRLF/CR to LF before applying the same validation sent to Semantic Core.

First success (`201 Created`) returns a note and source-backed candidates:

```json
{
  "requestId": "req-01",
  "note": {"id": "note-01", "recordedAt": "2026-07-31T10:00:00Z"},
  "candidates": [
    {"id": "cand-01", "sourceItemId": "item-01", "status": "extracted"},
    {"id": "cand-02", "sourceItemId": "item-02", "status": "extracted"}
  ]
}
```

An identical replay returns `200 OK` with exactly the original representation.
No retry, validation, or storage error may leave a partial capture visible.

## Candidate Review and Reads

| Method and path | Request / response |
|---|---|
| `POST /candidates/{candidateId}/validations` | Empty body; `200` validation result. |
| `POST /candidates/{candidateId}/confirmations` | `Idempotency-Key`; Requirement assertion label and valid-from date; `201` first decision, `200` replay. |
| `POST /candidates/{candidateId}/rejections` | `Idempotency-Key`; non-empty reason; `201` first decision, `200` replay. |
| `GET /knowledge-items/current?type=Requirement` | Current asserted items; type is optional and allowlisted. |
| `GET /candidates/{candidateId}/history` | Ordered lifecycle activities and current state. |
| `GET /knowledge-items/{itemId}/evidence` | Asserted item → candidate → source segment → Note → author chain, with offsets when released. |

FastAPI presents released review operations only; it performs no graph update.
Confirmation remains allowlisted to `Requirement`; rejecting never creates an
asserted item. Pagination, arbitrary filters, note edit/delete, inference
reads, and bulk review are out of scope.

## Implementation Preconditions

The capture route is enabled against the local v0.3 draft and its validation
evidence. A separate human release approval is still required before the
evidence extension is published as an ontology release.
