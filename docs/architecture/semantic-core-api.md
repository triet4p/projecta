# Semantic Core API Contract — Sprint 3

## 1. Scope and Boundary

This is the internal, domain-safe HTTP contract for the Semantic Core runtime
slice. It supports validation, confirmation, rejection, and three allowlisted
project views. It deliberately does not expose a SPARQL endpoint or generic
RDF graph mutation.

All endpoints are relative to `/v1`. JSON uses UTF-8 and timestamps use RFC
3339 UTC instants. IDs are opaque strings; their backing RDF IRIs are created
and routed only by the service.

## 2. Trusted Request Context

The service requires a `ProjectContext` established by trusted middleware or a
trusted internal caller:

```text
projectId: opaque project identifier
actorId: authenticated actor identifier
requestId: correlation identifier
```

`projectId` and `actorId` are not accepted in JSON payloads, path parameters,
or client-controlled headers. In Sprint 3, the caller-to-middleware trust
mechanism is deployment configuration, not an authentication feature. A
missing or malformed trusted context fails before endpoint processing.

## 3. Shared Response and Error Models

Every response has `requestId`. Errors use `application/problem+json`:

```json
{
  "type": "https://w3id.org/projecta/problems/validation-failed",
  "title": "Candidate does not conform",
  "status": 422,
  "code": "CANDIDATE_INVALID",
  "detail": "The candidate violates released v0.2 shapes.",
  "requestId": "req-01",
  "violations": [
    {
      "shape": "https://w3id.org/projecta/ontology/CandidateShape",
      "path": "https://w3id.org/projecta/ontology/proposedOntologyVersion",
      "message": "A Candidate must record the ontology version under which it was proposed."
    }
  ]
}
```

`violations` is present only for `CANDIDATE_INVALID`. The API never return raw
SPARQL, graph IRIs, internal Fuseki URLs, or stack traces.

| Code | HTTP | Meaning |
|---|---:|---|
| `PROJECT_CONTEXT_REQUIRED` | 401 | Trusted project context is absent or invalid. |
| `CANDIDATE_NOT_FOUND` | 404 | Candidate is not visible in the trusted project. |
| `RESOURCE_NOT_FOUND` | 404 | Allowlisted resource is not visible in the trusted project. |
| `INVALID_REQUEST` | 400 | JSON schema, header, or query parameter is invalid. |
| `CANDIDATE_INVALID` | 422 | Candidate does not conform to released shapes. |
| `INVALID_LIFECYCLE_STATE` | 409 | Requested transition is not allowed from current state. |
| `DECISION_CONFLICT` | 409 | A different terminal decision committed first. |
| `IDEMPOTENCY_KEY_REUSED` | 409 | A key is reused for a different operation, candidate, or request body. |
| `SERVICE_UNAVAILABLE` | 503 | Semantic store or required released artifacts are unavailable. |
| `INTERNAL_ERROR` | 500 | Unexpected error; no partial graph mutation is committed. |

## 4. Mutation Endpoints

### 4.1 Validate a candidate

`POST /candidates/{candidateId}/validations`

Request body is empty. The service reads the candidate only from the trusted
  project's candidates graph and validates it with the candidate, source, and
  evidence shapes available in the local ontology draft.

Success (`200 OK`):

```json
{
  "requestId": "req-01",
  "candidateId": "cand-123",
  "conforms": true,
  "violations": [],
  "validatedAt": "2026-07-29T10:00:00Z"
}
```

A non-conformant candidate returns `422 CANDIDATE_INVALID` with structured
violations. This endpoint has no idempotency-key requirement because it is
  read-plus-validation and promotes a conforming extracted candidate to
  `validated`. The promotion and its `prov:Activity` (including actor, project,
  candidate, and timestamp) are one conditional Fuseki update, so a failed or
  repeated transition cannot create a partial validation record.

### 4.2 Confirm a candidate

`POST /candidates/{candidateId}/confirmations`

Required header: `Idempotency-Key`, a 1–128 character opaque token. The body
may contain only presentation-free assertion fields allowed by the released
type mapping; the initial supported mapping is a Requirement label:

```json
{
  "assertion": {
    "type": "Requirement",
    "label": "Address confirmation before payment",
    "validFrom": "2026-07-29"
  }
}
```

Success (`201 Created`):

```json
{
  "requestId": "req-02",
  "candidateId": "cand-123",
  "decision": "confirmed",
  "assertedItem": {
    "id": "ki-456",
    "type": "Requirement",
    "label": "Address confirmation before payment",
    "validFrom": "2026-07-29"
  },
  "decidedAt": "2026-07-29T10:15:00Z"
}
```

The service revalidates before committing, then atomically writes the asserted
item, RDF-reified provenance, and lifecycle decision. A repeat with the same
project, endpoint, candidate, key, and canonical request body returns the
original response (`200 OK` on replay) and creates no new activity or item.

### 4.3 Reject a candidate

`POST /candidates/{candidateId}/rejections`

Required header: `Idempotency-Key`. Request body:

```json
{
  "reason": "The source does not establish whether this applies to saved addresses."
}
```

Success (`201 Created`):

```json
{
  "requestId": "req-03",
  "candidateId": "cand-123",
  "decision": "rejected",
  "reason": "The source does not establish whether this applies to saved addresses.",
  "decidedAt": "2026-07-29T10:16:00Z"
}
```

A valid replay returns the original response (`200 OK`). The transaction writes
the rejection decision and provenance only; it never writes an asserted item.

## 5. Allowlisted Read Endpoints

These endpoints bind the trusted project context server-side. Their query
surface is intentionally finite:

| Endpoint | Result | Backing lifecycle question |
|---|---|---|
| `GET /knowledge-items/current?type=Requirement` | Current asserted items of an allowed type | Current knowledge for a project |
| `GET /candidates/{candidateId}/history` | Ordered lifecycle activities and current state | CQ-LC-003 |
| `GET /knowledge-items/{itemId}/evidence` | Asserted item → candidate → source → reviewer chain | CQ-EV-002 |

`type` is optional and, when present, must be an allowlisted released type.
Collection responses use `200 OK` with `{ "requestId", "items" }`; a missing
item in a trusted scope returns `404 RESOURCE_NOT_FOUND`. Pagination and
arbitrary filtering are deferred until a separate API decision.

## 6. Idempotency Semantics

Idempotency applies to confirm and reject operations. The uniqueness scope is:

```text
trusted project + endpoint + candidate ID + Idempotency-Key
```

The server retains a canonical request fingerprint and finalized response. A
reuse with a changed body or a different candidate is `409 IDEMPOTENCY_KEY_REUSED`.
A key remains reserved after a terminal result, including a conflict result
caused by a competing decision.

The idempotency record is operational state, not asserted semantic truth. Its
physical storage is intentionally deferred to the selected service baseline;
S3-13/S3-14 must prove that it shares the decision transaction's effective
atomicity and survives the restart scenario required by S3-17.

## 7. HTTP Semantics and Non-Goals

- `201` denotes the first committed terminal decision; an idempotent replay is
  `200` with the original representation.
- `409` is recoverable by reading history; it must not reveal cross-project
  details.
- `422` means the candidate is syntactically addressable but semantically
  invalid under released v0.2 validation.
- No endpoint accepts arbitrary RDF, graph IRIs, SPARQL, reviewer IDs, project
  IDs, or a client-chosen asserted-item IRI.
- No delete, update, retraction, supersession, inference, bulk review,
  authentication, or authorization-management endpoint is in this contract.
