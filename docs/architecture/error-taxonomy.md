# Finite Error Taxonomy — Sprint 8

**Status:** `PROPOSAL_ONLY` — pending S8-11 architecture/security approval
**Task:** S8-03
**Scope:** Public Application API problems and normalized internal boundary
errors

## Purpose

This document freezes a finite error vocabulary for validation, configuration,
provider, timeout, persistence, SHACL, query, project-scope, and infrastructure
failures. The public code is stable product contract; the internal class adds
boundary and diagnostic precision without exposing provider payloads, source
text, SPARQL/RDF, graph IRIs, secrets, or stack traces.

The existing Sprint 4–7 public envelope remains the compatibility baseline:
`application/problem+json`, a safe `detail`, a stable `code`, and `requestId`.
S8-61 must regenerate the Application API snapshot after this proposal is
approved; until then, implementation must not silently claim the new codes are
already released.

## Error envelope

All non-2xx Application API responses use:

```json
{
  "type": "https://w3id.org/projecta/problems/<code>",
  "title": "Safe stable title",
  "status": 503,
  "code": "PROVIDER_TIMEOUT",
  "detail": "The configured provider did not respond before the deadline.",
  "requestId": "req-safe-opaque"
}
```

Rules:

- `requestId` is mandatory and is safe to return to the caller.
- `code` is an allowlisted machine-readable value; no provider/status text is
  interpolated into it.
- `detail` is bounded, user-safe, and contains no raw input, URL credentials,
  model payload, prompt, source excerpt, SPARQL, RDF, graph IRI, or stack trace.
- `type` is stable documentation metadata and must not encode an internal ID.
- Additional fields require an approved contract revision and must remain safe
  under the redaction rules below.

## Public taxonomy

| Public code | HTTP | Internal class(es) | Retryability | Terminal outcome | Mutation rule |
| --- | ---: | --- | --- | --- | --- |
| `INVALID_REQUEST` | 400 | `request.invalid`, `query.invalid`, `idempotency.malformed` | No | `rejected` | None. |
| `PROJECT_CONTEXT_REQUIRED` | 401 | `scope.context_missing`, `scope.context_invalid` | No automatic retry | `rejected` | None. |
| `PROJECT_FORBIDDEN` | 403 | `scope.forbidden` | No | `rejected` | None; do not reveal existence outside scope. |
| `RESOURCE_NOT_FOUND` | 404 | `scope.resource_not_visible`, `lifecycle.resource_missing` | No | `rejected` | None. |
| `PROJECT_SELECTION_STALE` | 409 | `scope.selection_revision_stale` | No automatic retry | `stale` | None; caller must select again. |
| `CANDIDATE_INVALID` | 422 | `semantic.candidate_invalid`, `validation.shacl_failed`, `validation.evidence_invalid` | No | `rejected` | Transaction rollback. |
| `INVALID_LIFECYCLE_STATE` | 409 | `lifecycle.transition_invalid` | No | `rejected` | None. |
| `DECISION_CONFLICT` | 409 | `lifecycle.terminal_decision_conflict` | No | `conflict` | Preserve existing terminal decision. |
| `IDEMPOTENCY_KEY_REUSED` | 409 | `idempotency.body_mismatch` | No | `conflict` | Preserve original operation; no second mutation. |
| `CONFIGURATION_INVALID` | 503 | `configuration.missing`, `configuration.invalid`, `configuration.secret_unavailable` | No automatic retry; operator/user may reconfigure | `blocked` | No activation or semantic mutation. |
| `PROVIDER_TIMEOUT` | 504 | `provider.timeout` | No implicit retry in interactive mode; explicit retry policy only | `failed` | None. |
| `PROVIDER_RATE_LIMITED` | 429 | `provider.rate_limited` | No implicit retry; caller may retry after explicit policy/metadata | `failed` | None. |
| `PROVIDER_UNAVAILABLE` | 503 | `provider.connection`, `provider.service`, `provider.network` | No implicit retry in interactive mode | `failed` | None. |
| `PROVIDER_RESPONSE_INVALID` | 502 | `provider.schema_invalid`, `provider.empty_malformed`, `provider.unsafe_output` | No | `failed` | None. |
| `PROVIDER_REFUSED` | 502 | `provider.refusal`, `provider.policy_rejection` | No | `failed` | None. |
| `SEMANTIC_VALIDATION_FAILED` | 422 | `semantic.shacl_failed`, `semantic.lifecycle_validation` | No | `rejected` | Transaction rollback. |
| `SEMANTIC_CORE_UNAVAILABLE` | 503 | `semantic_core.connection`, `semantic_core.timeout`, `semantic_core.not_ready` | No implicit retry; explicit user retry only | `failed` | None. |
| `SEMANTIC_CORE_CONTRACT_INVALID` | 502 | `semantic_core.response_invalid`, `semantic_core.version_mismatch` | No | `failed` | None. |
| `PERSISTENCE_UNAVAILABLE` | 503 | `persistence.database`, `persistence.tdb2`, `persistence.transaction` | No implicit mutation retry | `failed` | Rollback/atomic failure boundary. |
| `QUERY_FAILED` | 502 | `query.execution`, `query.result_invalid`, `query.limit_invalid` | No implicit retry | `failed` | None. |
| `INFRASTRUCTURE_UNAVAILABLE` | 503 | `infrastructure.upstream`, `infrastructure.health`, `infrastructure.compose` | No automatic retry at public boundary | `blocked` | None. |
| `INTERNAL_ERROR` | 500 | `internal.unclassified`, `internal.unexpected` | No | `failed` | Rollback where applicable. |

`SEMANTIC_CONTRACT_UNAVAILABLE` from the released Sprint 4–7 contract remains
a compatibility alias for the subset of `SEMANTIC_CORE_UNAVAILABLE`,
`SEMANTIC_CORE_CONTRACT_INVALID`, and provider/dependency failures until the
approved Sprint 8 Application API snapshot replaces it. It must not be used
as a new catch-all in implementation.

## Internal normalized classes

Internal events use a two-part class: `<boundary>.<reason>`. The following
allowlist is closed for Sprint 8:

| Boundary | Allowed reasons |
| --- | --- |
| `request` | `invalid`, `unsupported_media_type`, `response_schema_invalid` |
| `scope` | `context_missing`, `context_invalid`, `forbidden`, `resource_not_visible`, `selection_stale`, `cross_project` |
| `configuration` | `missing`, `invalid`, `secret_unavailable`, `mode_invalid`, `profile_conflict` |
| `provider` | `timeout`, `rate_limited`, `connection`, `service`, `network`, `schema_invalid`, `empty_malformed`, `refusal`, `policy_rejection`, `unsafe_output` |
| `semantic_core` | `connection`, `timeout`, `not_ready`, `response_invalid`, `version_mismatch`, `unexpected` |
| `semantic` | `candidate_invalid`, `shacl_failed`, `lifecycle_validation`, `evidence_invalid`, `provenance_invalid` |
| `persistence` | `database`, `tdb2`, `transaction`, `idempotency_store`, `rollback_failed` |
| `query` | `execution`, `result_invalid`, `limit_invalid`, `filter_invalid`, `arbitrary_query_rejected` |
| `infrastructure` | `upstream`, `health`, `compose`, `proxy_timeout`, `image_invalid` |
| `lifecycle` | `transition_invalid`, `terminal_decision_conflict`, `resource_missing` |
| `idempotency` | `malformed`, `body_mismatch`, `replay_invalid` |
| `internal` | `unclassified`, `unexpected` |

Unknown internal exceptions are normalized to `internal.unclassified` at the
boundary and never serialized verbatim.

## Mapping rules by boundary

| Boundary | Mapping responsibility | Must preserve |
| --- | --- | --- |
| Browser client | Validate content type, JSON, request ID, and typed success before rendering. | Public `code`, `status`, `requestId`, and explicit result state. |
| Nginx | Preserve valid upstream problem; map proxy timeout/connection failure to a finite infrastructure problem without inventing success. | Request ID, route class, upstream outcome, safe body. |
| Application API | Map trusted context, request validation, provider/orchestration, persistence, and Core errors to public codes. | No internal class leakage; no loss of terminal outcome or mutation semantics. |
| Semantic Core | Normalize parse/validation/lifecycle/Fuseki/TDB2 errors to a typed response. | Project-safe scope, semantic/lifecycle identity, and rollback status. |
| Fuseki gateway | Convert query/update transport/result failures to `persistence.*` or `query.*`. | Operation kind, timeout, result cardinality, but never query/RDF payload. |
| Provider adapter | Convert SDK/network/status/refusal/schema outcomes to `provider.*`. | Attempt number, timeout, model/profile revision, safe normalized class. |
| Compose probes | Report process liveness separately from readiness/dependency health. | Probe command, dependency, exit evidence, and ready/not-ready truth. |

## Retryability and terminal outcome

`retryability` is one of `none`, `explicit_user_action`,
`reviewed_bounded_mode`, or `operator_recovery`. It is not inferred solely from
HTTP status. Interactive extraction defaults to `none` and is governed by
S8-05.

`terminalOutcome` is one of:

- `success`: typed domain result, including a permitted empty result;
- `abstained`: successful extraction with no candidate and explicit reason;
- `rejected`: caller/request/semantic validation refused;
- `stale`: revision or selection is no longer current;
- `conflict`: an existing idempotent/terminal decision wins;
- `failed`: dependency or unexpected operation failure;
- `blocked`: configuration/readiness prevents operation before mutation.

The event and public problem must use the same terminal outcome. A response
cannot say `success` while its operation event says `failed`.

## Redaction contract

### Never expose

- credentials, API keys, authorization headers, secret references, or hashes;
- provider request/response payloads, prompts, raw note/source text, or full
  evidence snippets;
- SPARQL, RDF/Turtle, graph IRIs, TDB2 paths, internal URLs, or storage paths;
- stack traces, exception messages containing input, and cross-project IDs;
- internal database keys, opaque IDs as primary error detail, or arbitrary query
  text.

### Safe fields

- public code, title, status, request ID;
- bounded field/path names for caller validation;
- retryability category and explicit operator/user action;
- sanitized provider host identity only when policy allows it;
- project-safe scope token or redacted project label;
- latency/attempt count only in logs/diagnostics, not raw provider detail.

## Regression requirements

- Every public code has a contract test for HTTP status, content type, safe
  envelope, request ID, and absence of forbidden fields.
- Every internal class has one normalization test and one mapping test.
- Timeout, rate limit, malformed provider output, Core 4xx/5xx, Fuseki failure,
  stale selection, SHACL rollback, and idempotency conflict all assert no
  semantic mutation.
- Unknown exception payloads are tested for safe `INTERNAL_ERROR` mapping.
- The generated API snapshot must include only approved codes after G1; drift
  fails validation.

## Review status

This taxonomy is the S8-03 proposal input to the S8-10 packet. S8-04 must
define how the fields are logged, S8-05 must finalize retry policy, and S8-06
must finalize scope-related status distinctions. The document remains
`PROPOSAL_ONLY` until S8-11 approval.
