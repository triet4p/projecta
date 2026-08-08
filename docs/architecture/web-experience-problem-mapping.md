# Web Experience Problem Mapping — Sprint 7

**Status:** IMPLEMENTATION_BASELINE
**Task:** S7-09

## Purpose

The web client must render stable user outcomes from the finite Application API
problem surface. It must not branch on exception text, provider payloads,
Semantic Core internals, or arbitrary response fields. Every outcome retains
the sanitized `requestId` for support and diagnostics.

## Public Problem Mapping

| Code | HTTP | User outcome | Retry | Field behavior |
|---|---:|---|---|---|
| `PROJECT_CONTEXT_REQUIRED` | 401 | “This local Projecta experience is not available or has no trusted project context.” Block project data and mutation controls. | No automatic retry; setup/restart guidance. | No project/actor detail beyond safe local-profile status. |
| `INVALID_REQUEST` | 400 | “Check the highlighted fields or selection.” Keep safe unsent form data. | Retry after correction. | Use structured field paths only when explicitly provided; otherwise show a generic contract message. |
| `RESOURCE_NOT_FOUND` | 404 | “This item is not available in the current project.” | Refresh/restart the current workflow. | Never say whether the ID exists in another project. |
| `CANDIDATE_INVALID` | 422 | “This candidate failed semantic validation.” Keep violations and disable confirmation. | No blind retry; allow review/rejection. | Render sanitized shape/path/message violations only. |
| `INVALID_LIFECYCLE_STATE` | 409 | “This candidate has changed state and cannot take that action.” | Refresh history once, then require user action. | Do not reveal graph state or another actor’s private details. |
| `DECISION_CONFLICT` | 409 | “Another terminal decision was recorded first.” | Refresh history once. | Render known terminal state only. |
| `IDEMPOTENCY_KEY_REUSED` | 409 | “This operation key was already used for different content.” Stop automatic resubmission. | No automatic retry with the same key. | Never display request fingerprints or stored bodies. |
| `SEMANTIC_CONTRACT_UNAVAILABLE` | 503 | “Project knowledge service is temporarily unavailable.” Preserve safe input and show request ID. | Bounded user retry. | No stack trace, Fuseki URL, graph name, SPARQL, or provider detail. |
| `UNKNOWN_INTENT` | 400 | “Ask about current requirements, requirement history, or unresolved blockers.” | Retry after editing the question. | Do not echo sensitive question text in telemetry. |
| `UNSUPPORTED_FILTER` | 400 | “That filter is not supported.” | Retry with the supported bounded controls. | Do not offer arbitrary query/filter controls. |
| `AMBIGUOUS_MATCH` | 400 | “Name one requirement to view its history.” | Retry after clarification. | Do not reveal candidate/entity matches outside the project. |
| `CROSS_PROJECT_ACCESS` | 400 | “Questions must stay within the current project.” | Retry with current-project wording. | Never confirm whether the named foreign project exists. |

Retrieval `no_evidence`, `stale_projection`, and similar conditions may be
represented by a successful M4 answer with `abstained`, `complete`, `meta`, or
`warnings` rather than a problem response. The client must inspect the typed
answer result before deciding that an operation failed.

## Screen State Mapping

| Screen | Loading | Empty/success | Recoverable failure | Blocking failure |
|---|---|---|---|---|
| Shell/diagnostics | Dependency check skeleton | Local profile and sanitized health status | Show dependency retry and request ID | Hide project data on missing trusted context. |
| LLM settings | Disable save/test while submitting | Redacted metadata and credential-configured status | Preserve prior profile; clear credential field; show retry | Disable extraction when no active usable profile exists. |
| Extraction | Keep note editable; disable duplicate submit | Candidate cards, evidence, links, or explicit abstention | Retry with preserved note and operation state | Context/configuration unavailable; do not show partial candidates. |
| Manual capture | Disable capture while validating spans | Note/candidates and replay indicator inferred from status | Inline span correction or bounded dependency retry | Context/semantic service unavailable; preserve unsent text only. |
| Candidate review | Disable duplicate decision | Validation violations, lifecycle state, Requirement confirmation or rejection | Refresh history on conflict; show terminal state | Candidate not visible, invalid, or unsupported transition. |
| Knowledge/evidence | Skeleton with opaque resource ID | Bounded items, history, evidence/provenance | Retry read; show project-scoped not-found | Context unavailable or response contract invalid. |
| Grounded Q&A | Disable submit while interpreting/retrieving | Answer facts, citations, status, derivation, freshness | Show warnings/abstention as answer state; retry unavailable dependency | Context or contract failure; no unsupported free-form query path. |

## Request ID and Retry Rules

- Every operation displays or makes a support-details affordance for the
  sanitized request ID.
- Generate one idempotency key per semantic operation and retain it through a
  bounded retry. A `200` replay is a successful completion, not an error.
- Never retry a `409 IDEMPOTENCY_KEY_REUSED` with the same key.
- Do not retry malformed input, invalid lifecycle state, candidate invalidity,
  or unsupported retrieval intent automatically.
- Retry `503` only with bounded backoff and only while the user operation is
  still active. Do not replay raw credentials from browser state or telemetry.

## Forbidden Client Behavior

- Branching on raw exception strings or provider-specific status text.
- Showing raw response bodies, stack traces, graph IRIs, storage URLs, SPARQL,
  secret references, or trusted headers.
- Treating a successful empty/abstained answer as an HTTP failure.
- Enabling confirmation for any candidate assertion type other than
  `Requirement`.
- Selecting project, actor, reviewer, tenant, graph, or arbitrary query scope.
