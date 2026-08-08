# Web Experience API Gap Audit — Sprint 7

**Status:** PROPOSED — pending S7-07 architecture/security review
**Task:** S7-03

## Scope

This audit compares the released M2–M4 Application API with the Sprint 7 web
journey and capability matrix. It identifies contract work required for a
truthful browser experience. It does not add ontology terms, semantic routes,
arbitrary filters, or client-controlled project identity.

The current implementation source is the FastAPI router and models in
`apps/api/src/projecta_api/`, the Semantic Core HTTP contract, and the released
M2–M4 use cases. The versioned frontend snapshot and generated client remain
future S7-08 artifacts.

## Gap Summary

| ID | Boundary | Current evidence | Gap and impact | Resolution owner |
|---|---|---|---|---|
| API-01 | Interactive LLM settings | `Settings` requires `PROJECTA_LLM_*` at composition time; no settings route or repository exists. | The user cannot configure or rotate a provider from the web app. | S7-06, S7-10–S7-20 |
| API-02 | Trusted browser context | `trusted_context` reads project/actor/request headers and a context secret; the documented deployment adapter is not implemented as a browser-safe same-origin boundary. | Direct browser calls could become client-controlled project routing unless a server/proxy strips and injects context. | S7-05, S7-24 |
| API-03 | Readiness and diagnostics | FastAPI exposes `/health/live`; Semantic Core has `/health/ready`, but it is not exposed through the Application API. | The shell cannot distinguish API liveness from usable semantic/provider dependencies. | S7-09, S7-28, S7-35 |
| API-04 | Candidate reload/recovery | Capture/extraction return candidate IDs; history is addressed by candidate ID; there is no candidate collection or detail route. | A browser reload cannot reliably recover an in-progress review journey. | S7-03 decision; add only if required and approved. |
| API-05 | Public response typing | Most FastAPI routes return `object`; only manual capture has a public response model. | OpenAPI and generated frontend types cannot safely freeze response fields or prevent internal metadata drift. | S7-03, S7-08 |
| API-06 | Error taxonomy alignment | Core/application errors use stable public codes; retrieval currently maps several typed errors to `400`, while successful no-evidence answers may be `200` with `abstained/warnings`. | UI cannot map every retrieval outcome consistently without a versioned public problem/result contract. | S7-03, S7-09 |
| API-07 | Collection limits and ordering | M4 query limits and stable ordering are released; M2 current/history/evidence reads do not expose pagination or consistent client limits. | Large-result behavior and loading states are not contractually bounded for all screens. | S7-03; do not invent pagination in the UI. |
| API-08 | Internal orchestration route | `/v1/entities/link-context` is exposed by the Application API to any caller with trusted context, although it exists to support extraction. | It could be mistaken for arbitrary entity search and expands the browser contract unnecessarily. | S7-03, S7-08; classify internal or replace with server-only call. |
| API-09 | Inference rebuild authority | `/v1/project-context/inference/rebuild` is callable through the Application API with trusted context but has no experience-mode authorization seam. | A normal user screen could accidentally become an admin/operational mutation surface. | S7-05, S7-35 |
| API-10 | Request/idempotency recovery | Idempotency is released for capture/extraction/decisions, but the public client contract does not define a generic operation status or recovery endpoint. | The UI must preserve operation keys and interpret replay/conflict without assuming failure means no mutation. | S7-03, S7-27 |
| API-11 | Settings and operation audit | Extraction/retrieval telemetry exists; configuration-change audit fields and secret-leak assertions do not. | Settings changes cannot yet be proven safe or attributed. | S7-06, S7-23, S7-38, S7-43 |
| API-12 | Cross-origin/browser delivery | Compose has no web service, same-origin proxy, CORS policy, or frontend image. | The API cannot yet be safely consumed by the intended static SPA topology. | S7-04, S7-37 |

## Existing Capability Contract

The following released routes are sufficient for the first semantic workflow if
the UI stays within their limits:

| Screen/action | Route | Contract dependency |
|---|---|---|
| Extract note | `POST /v1/quick-notes/extractions` | `m3.v1`, exact evidence, bounded links, idempotency, abstention. |
| Manual capture | `POST /v1/quick-notes` | Ordered/non-overlapping Unicode-code-point spans, idempotency. |
| Validate | `POST /v1/candidates/{candidateId}/validations` | Validation result and lifecycle promotion to `validated`. |
| Confirm | `POST /v1/candidates/{candidateId}/confirmations` | `Requirement` only; first decision `201`, replay `200`. |
| Reject | `POST /v1/candidates/{candidateId}/rejections` | Reason required; first decision `201`, replay `200`. |
| Current knowledge | `GET /v1/knowledge-items/current?type=Requirement` | Project-scoped asserted items; no pagination/arbitrary filters. |
| Candidate history | `GET /v1/candidates/{candidateId}/history` | Opaque ID required; no candidate discovery. |
| Evidence | `GET /v1/knowledge-items/{itemId}/evidence` | Opaque ID and bounded provenance/evidence chain. |
| Grounded Q&A | `POST /v1/project-context/answers` | M4 allowlisted intents only; structured facts/citations/freshness. |

## Required Contract Decisions Before Client Generation

S7-07 must review these choices before S7-08 freezes an OpenAPI snapshot:

- Whether candidate reload recovery is explicitly out of scope for this slice
  or requires a new bounded list/detail route.
- Whether link-context is removed from the public client contract and kept as a
  server-to-Core orchestration operation.
- The public readiness/diagnostics shape and whether inference rebuild is
  available only in the local experience profile.
- Exact response models for extraction, validation, decisions, reads, and
  rebuild; internal `_projecta_http_status` metadata must never enter the
  snapshot.
- Stable retrieval problem codes versus successful `200` answers carrying
  `abstained`, `complete`, `partial`, `stale`, or `warnings` state.
- Request correlation and idempotency replay/conflict behavior for generated
  client helpers.

## Non-Gaps / Do Not Expand

- M2/M3 candidate persistence remains candidate-only until human review.
- Requirement-only confirmation is intentional; other assertion types are not
  a missing UI feature.
- The browser does not need direct Semantic Core, Fuseki, SPARQL, graph IRI,
  RDF, or storage access.
- Authentication provider, RBAC/ABAC, tenant administration, connector APIs,
  and desktop packaging are Sprint 8+ concerns.
- No ontology or SHACL change is justified by this audit.

## References

- [Web Experience Use Case](../use-cases/web-experience.md)
- [Web Experience Capability Matrix](web-experience-capability-matrix.md)
- [Application API Contract](application-api.md)
- [M3 Extraction Error Taxonomy](llm-extraction-errors.md)
- [M4 Semantic Retrieval Contract](semantic-retrieval.md)
