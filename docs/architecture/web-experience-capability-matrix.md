# Web Experience Capability Matrix — Sprint 7

**Status:** IMPLEMENTATION_BASELINE
**Task:** S7-02

## Purpose

This matrix maps the released Application API and Semantic Core capabilities to
the Sprint 7 screens and actions. It is intentionally more concrete than the
web journey and less final than the versioned frontend API snapshot planned in
S7-08. S7-03 must resolve the contract gaps identified here before the client
types are frozen.

The browser calls only the Application API. The Application API establishes
trusted context, validates public input, and forwards finite operations. The
Semantic Core remains the only service that routes RDF graphs or performs
semantic mutation.

## Shared Rules

| Rule | Current behavior | UI consequence |
|---|---|---|
| Trusted context | Every project-scoped route requires deployment-established project, actor, and request context. The current local adapter verifies a shared secret before accepting context headers. | Never render a project/actor override control or send the trust secret from browser code. Missing context is a blocking `401`. |
| Correlation | Successful Application API responses set `X-Request-Id`; problem responses include `requestId`. | Keep the request ID with the operation result and show it in diagnostics/support details. |
| Idempotency | Capture, extraction, confirmation, and rejection require an opaque `Idempotency-Key`. Validation and reads do not. | Generate one key per user operation, disable duplicate submit, and treat `200` replay as success. |
| Error boundary | Public errors are RFC 7807-shaped and sanitized. Provider/model failures are not exposed as provider payloads. | Map finite codes to user outcomes; never display stack traces, graph names, storage URLs, or raw provider details. |
| Scope | Project IDs, RDF IRIs, graph IRIs, reviewer IDs, arbitrary filters, and SPARQL are server-owned or forbidden. | UI state may retain opaque IDs only; no free-form query or identity routing controls. |

## Screen and Endpoint Matrix

| Screen/action | Application endpoint | Request and headers | Success response/state | Error handling and backend limitation |
|---|---|---|---|---|
| App shell: liveness | `GET /health/live` | No project context required. | `200 {"status":"live"}`. | This is process liveness only. FastAPI has no public readiness/dependency endpoint yet; S7-35 needs a separate sanitized diagnostics capability. |
| Settings: read active profile | **Missing — S7 API** | Provider metadata, active revision, `credentialConfigured`, and health status only. | Redacted profile metadata. | No current route, repository, or secret-store port exists. Do not build the screen against environment-file editing. |
| Settings: create/update/rotate/remove | **Missing — S7 API** | Provider type, base URL, model, and credential input over a server-owned boundary. | Redacted status; never raw credential. | Must be defined after S7-06/S7-14. Invalid input, unavailable store, concurrency conflict, and cleanup behavior need stable codes. |
| Settings: connection check | **Missing — S7 API** | Bounded provider/model check; no semantic mutation. | Sanitized reachable/configured result. | No current route. Must not expose provider response body, credential, or sensitive URL components. |
| Quick Note: extract | `POST /v1/quick-notes/extractions` | JSON `{rawText, extractionVersion:"m3.v1"}` plus `Idempotency-Key`. Trusted context is server-established. | `201` first result or `200` replay. Returns request ID, opaque note ID, and candidate results. Candidates contain normalized entity/relation/link proposals, evidence, and explicit abstention where applicable. | `400` invalid request; `401` missing context; `503` sanitized gateway/normalization/semantic failure; `409` idempotency conflict. No candidate is persisted on invalid provider output. Live provider quality is not guaranteed by this route. |
| Quick Note: manual typed capture | `POST /v1/quick-notes` | JSON `{rawText, segments[]}` plus `Idempotency-Key`. Each segment is an ordered, non-overlapping exact Unicode-code-point span. | `201` first capture or `200` replay. Returns `requestId`, note, and opaque candidate IDs/statuses. Candidates begin as `extracted` and become reviewable. | `400` empty/unknown/malformed/mismatched spans; `401` context; `409` idempotency conflict; `503` semantic service failure. No edit/delete, bulk capture, or partial mutation. |
| Candidate: validate | `POST /v1/candidates/{candidateId}/validations` | Empty body; trusted context; no idempotency key. | `200` validation result with candidate ID, `conforms`, violations, and validation time. A conforming candidate is promoted to `validated`. | `404` candidate not visible in project; `422 CANDIDATE_INVALID`; `409` invalid lifecycle state; `503` semantic unavailable. Validation is a mutation of lifecycle/provenance state even though the request body is empty. |
| Candidate: confirm | `POST /v1/candidates/{candidateId}/confirmations` | `{assertion:{type:"Requirement",label,validFrom}}` plus `Idempotency-Key`. | `201` first decision or `200` replay. Returns confirmed decision and opaque asserted-item ID. Candidate becomes confirmed/asserted and a Requirement is written to asserted knowledge. | `400` malformed assertion; `404` inaccessible candidate; `409` lifecycle/idempotency/decision conflict; `422` semantic invalidity; `503` unavailable. **Only `Requirement` confirmation is supported.** The UI must not offer confirmation for other candidate types. |
| Candidate: reject | `POST /v1/candidates/{candidateId}/rejections` | `{reason}` plus `Idempotency-Key`. | `201` first decision or `200` replay. Candidate becomes rejected; response includes candidate ID, decision, and reason. | `400` empty/oversized reason; `404` inaccessible candidate; `409` lifecycle/idempotency/decision conflict; `503` unavailable. Rejection creates no asserted item. |
| Knowledge: current items | `GET /v1/knowledge-items/current?type=Requirement` | Optional allowlisted `type`; trusted context. | `200 {requestId,items[]}`. Current asserted items are returned with opaque IDs and released fields. | `400` invalid type; `401` context; `404` only when a requested opaque resource is not visible; `503` unavailable. Pagination and arbitrary filters are not available. |
| Candidate: history | `GET /v1/candidates/{candidateId}/history` | Opaque candidate ID; trusted context. | `200 {requestId,items[]}` ordered lifecycle activities and current state. | `404` inaccessible/missing candidate; `503` unavailable. There is no current candidate collection or candidate detail endpoint, so reload/recovery requires a retained opaque ID. |
| Knowledge: evidence | `GET /v1/knowledge-items/{itemId}/evidence` | Opaque asserted-item ID; trusted context. | `200 {requestId,items[]}` evidence/provenance chain from asserted item through candidate/source, including released offsets. | `404` inaccessible/missing item; `503` unavailable. No raw graph/storage URI or unrestricted source browser. |
| Project Q&A | `POST /v1/project-context/answers` | `{question,limit}`; `limit` is 1–100; trusted context. | `200` `m4.v1` answer: bounded query intent, text, facts, citations, asserted/inferred status, derivations, freshness metadata, `complete`, `abstained`, and warnings. | `400` unknown intent, unsupported filter, ambiguity, invalid entity, no evidence, stale/rule/provider/dependency errors as mapped by current retrieval boundary; `401` context; `503` downstream failure. Only current requirements, requirement history, and unresolved blockers are supported. No arbitrary SPARQL or general Q&A. |
| Diagnostics: inference rebuild | `POST /v1/project-context/inference/rebuild` | Empty body; trusted context. | `200` deterministic rebuild metadata including source/materialization revisions and materialized rule IDs. | Current route is backend-supported but not yet an experience-authorized admin capability. S7-35 must gate it as local experience-only and hide it in production. It must not be presented as ordinary user content mutation. |
| Internal extraction support: entity link context | `GET /v1/entities/link-context?limit=50` | Trusted context; bounded limit 1–100. | `200 {requestId,entities[]}` with same-project opaque IDs, types, and labels. | This is an orchestration support route, not a browser screen. It must not be exposed as arbitrary entity search or allow cross-project lookup. |

## Lifecycle State Mapping

The UI should render state from returned lifecycle data rather than infer it
from button history.

| State or result | Meaning | Allowed next UI action |
|---|---|---|
| `extracted` | Candidate was created by M2/M3 capture and awaits review. | Validate, then review; reject is allowed through the released lifecycle. |
| `validated` | Candidate passed released semantic validation. | Confirm only when the candidate is eligible for the Requirement assertion; reject remains available if the lifecycle allows it. |
| `pending-review` | Reviewable candidate state returned by the public candidate model. | Show review controls; do not treat it as asserted knowledge. |
| `confirmed` / `asserted` | Candidate decision produced an asserted knowledge item. | Read current knowledge and evidence; no edit/delete/retraction action exists. |
| `rejected` | Candidate was rejected with a reason. | Show reason and history; no confirmation action. |
| `asserted` fact | M4 fact backed by asserted project knowledge. | Show citations/evidence. |
| `inferred` fact | M4 fact materialized by an approved rule. | Show rule ID/version, derivation input IDs, freshness, and warnings. |
| `abstained` answer/extraction | No safe proposal or grounded answer was produced. | Show explicit empty/abstained state; do not convert it into an error or fact. |

## Cross-Cutting Public Error Mapping

The current Application API exposes the following stable user-facing classes.
The exact frontend payload and field-level extensions are an S7-03/S7-09 gap,
not a reason for screens to inspect arbitrary exception text.

| Code | HTTP | Screens/actions |
|---|---:|---|
| `PROJECT_CONTEXT_REQUIRED` | 401 | Block all project screens; show local-context/setup guidance. |
| `INVALID_REQUEST` | 400 | Inline form/span/query errors; preserve safe unsent input. |
| `RESOURCE_NOT_FOUND` | 404 | Show resource unavailable in this project; do not reveal whether it exists elsewhere. |
| `CANDIDATE_INVALID` | 422 | Show validation violations; disable confirmation until resolved or rejected. |
| `INVALID_LIFECYCLE_STATE` | 409 | Refresh known candidate history and disable the invalid transition. |
| `DECISION_CONFLICT` | 409 | Show that another terminal decision won; render the known terminal state. |
| `IDEMPOTENCY_KEY_REUSED` | 409 | Stop automatic resubmission; require a new operation or recover the original request. |
| `SEMANTIC_CONTRACT_UNAVAILABLE` | 503 | Retryable dependency state; show request ID without internal details. |
| Retrieval taxonomy errors | Interpreter failures such as unknown intent, unsupported filter, ambiguity, and cross-project rejection currently become bounded `400` failures. No-evidence can instead be a successful `200` abstained answer with warnings; stale/rule/dependency outcomes need contract review. | Map each outcome distinctly once S7-09 freezes public codes and success-with-warning behavior. Do not treat every empty or abstained answer as an HTTP error. |

## Missing or Restricted Capabilities

These are intentional implementation inputs for S7-03 and later tasks:

- No settings read/write/rotate/delete or connection-check API exists.
- No Application API readiness/dependency-health surface exists; `/health/live`
  proves only process liveness.
- No candidate list/detail endpoint exists. The current journey can continue
  from IDs returned by capture/extraction, but browser reload recovery is not a
  released capability.
- Current read contracts do not provide pagination or arbitrary filtering.
- Most routes return `object` from FastAPI rather than explicit public response
  models; the frontend snapshot must freeze the actual safe fields before code
  generation.
- Inference rebuild exists but is not yet an experience-mode authorization
  boundary or production-disabled diagnostics action.
- Candidate confirmation is explicitly Requirement-only. Supporting other
  assertion types requires a separate semantic/product decision and must not be
  approximated in the UI.
- Authentication, authorization administration, tenant management, and
  production identity selection are not delivered by this matrix.

## Source Contracts

- [Web Experience Use Case](../use-cases/web-experience.md)
- [Application API Contract](application-api.md)
- [Semantic Core API Contract](semantic-core-api.md)
- [M2 Quick Note Use Case](../use-cases/quick-note.md)
- [M3 LLM Candidate Extraction Use Case](../use-cases/llm-candidate-extraction.md)
- [M4 Project Context Question](../use-cases/project-context-question.md)
