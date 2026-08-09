# Fail-Explicit Runtime Contract — Sprint 8

**Status:** `PROPOSAL_ONLY` — pending S8-11 architecture/security approval
**Task:** S8-02
**Scope:** Web, Nginx, Application API, Semantic Core, Fuseki, provider
adapters, and Compose health boundaries

## Purpose

This contract distinguishes a domain-valid empty or abstained result from an
operational failure. A dependency failure must never be converted into an
empty collection, `null`, `{}`, `unknown`, `unavailable`, partial success, a
default authority, a provider switch, or a hidden retry. The exact public
problem codes are defined by S8-03; this document defines the behavior that
those codes must preserve.

This is a reviewable design artifact. It does not approve an ontology change,
production authorization model, or implementation of a new fallback.

## Definitions

### Domain-valid empty

A successful operation whose contract permits zero domain records and whose
dependencies completed successfully. Examples include an empty authorized
project catalog, an empty bounded graph projection, no current requirements, or
an extraction abstention with a recorded safe activity outcome.

### Explicit abstention

A successful extraction outcome in which the provider or deterministic policy
deliberately produced no candidate because evidence was insufficient or
ambiguous. It is not a provider error and must remain visibly distinct from a
transport, schema, validation, or persistence failure.

### Operational failure

Any missing, unavailable, malformed, unauthorized, timed-out, inconsistent, or
unexpected dependency/contract result. It returns a finite non-2xx problem at
the owning public boundary, records one correlated terminal event, and does
not create semantic mutation unless the operation contract explicitly says a
durable failure record is part of the failure path.

### Explicit user action

A new user command such as selecting a project, pressing retry, reloading a
collection, or choosing replay/test mode. A prior failed request cannot create
that action implicitly.

## Boundary matrix

| Boundary | Domain-valid empty/success | Must fail explicitly | Forbidden substitution | Required evidence |
| --- | --- | --- | --- | --- |
| Web client | Renders a typed empty collection, explicit abstention, cancellation, loading, or stale state when the API returned that state. | Non-JSON, wrong content type, missing request ID, schema drift, malformed success, or API problem. | Empty screen after a fetch failure; generic success after invalid JSON; implicit provider/replay retry; local-project reversion. | Client contract test and browser failure journey preserve code/request ID/outcome. |
| Nginx same-origin boundary | Proxies a valid upstream response without changing its problem/result semantics. | Upstream connection failure, timeout, invalid upstream body, or unavailable route. | Synthesized JSON `{}`/`[]`; cached stale success; dropped request ID; exposed upstream stack trace or body. | Structured access/error event with request ID, route class, upstream status, latency, and outcome. |
| Application API | Returns a typed zero-item collection, explicit abstention, deterministic inference result, or idempotent replay only when the downstream contract completed successfully. | Missing trusted context, invalid composition, dependency outage, invalid downstream contract, provider failure, persistence/SHACL failure, or unknown exception. | Optional service becomes empty service; `200` success after downstream failure; default project/actor/provider; raw exception; partial semantic mutation. | Public `application/problem+json`, stable code, request ID, no sensitive detail, no mutation on failed write. |
| Semantic Core | Returns zero rows/items when the bounded query/lifecycle operation succeeded and the finite contract permits zero. | Invalid request, authorization/project scope failure, SHACL/lifecycle violation, Fuseki/TDB2 failure, invalid response, or unexpected exception. | Empty query result after store failure; generic success body; cross-project data; graph/storage identifier leakage. | Typed non-2xx response and operation start/terminal events with project-safe scope. |
| Fuseki/TDB2 | Zero result cardinality from a successful allowlisted query/update is valid. | Connection failure, timeout, malformed result, transaction failure, unavailable dataset, or ownership conflict. | Treating an absent/invalid response as zero rows; retrying a mutation without idempotency contract; exposing SPARQL/RDF payloads. | Safe gateway diagnostics with operation kind/status/latency/timeout/result cardinality. |
| Provider adapter | Structured abstention is a successful extraction result if the adapter contract says so; a bounded deterministic inference result is also valid. | Timeout, rate limit, connection/status failure, refusal, empty malformed output, schema violation, unsafe link/evidence, or invalid configuration. | Switching provider, model, base URL, replay fixture, or prompt mode after failure; storing raw note as a fallback; retrying outside approved mode. | One provider-attempt start/terminal event; normalized private class and public sanitized problem. |
| Compose health/readiness | Liveness reports process health; readiness reports whether declared dependencies/contracts are usable. A dependency may be not-ready while the process is live. | Failed probe, missing required config, dependency unavailable, invalid image/config, or unhealthy required service. | Marking not-ready healthy; hiding probe exit evidence; starting a write-capable service with an invalid semantic boundary. | Probe result, dependency, exit evidence, and diagnostic command in operator runbook. |

## Explicit processing rules

The following values must be selected by deployment configuration, a reviewed
server-side policy, or a visible user action. They may not be inferred from a
failed request:

| Processing choice | Allowed source | Prohibited implicit behavior |
| --- | --- | --- |
| Provider, endpoint, and model | Required runtime configuration or approved experience profile | Provider/model/base-URL fallback after a live failure. |
| Retry count and delay | Reviewed operation mode and bounded policy | Automatic retry added by a generic client or hidden from the user/event stream. |
| Replay/test mode | Explicit deployment/test configuration or explicit test command | Activating replay after provider timeout, schema failure, or rate limit. |
| Project and actor scope | Server-established context and finite authorized catalog | Browser-selected trusted headers, arbitrary project ID, stale-selection fallback to `local-project`. |
| Persistence and semantic version | Loaded approved ontology/shapes and named-graph contract | Saving raw/partial data when structure, SHACL, or dependency validation fails. |
| Inference rebuild | Explicit operational command with deterministic rules | Running a rebuild because a read failed or presenting inferred data as asserted. |
| Background work | Declared job contract with visible state | Spawning hidden work from a failed request or returning success before required commit. |

## Result-state rules

Every public operation must make the following states distinguishable:

| State | HTTP/result behavior | Mutation rule |
| --- | --- | --- |
| `loading` | Client-only transient state; no API success claim. | None. |
| `success` | Typed response, including a typed empty domain when permitted. | Commit only according to the operation contract. |
| `abstained` | Typed successful extraction result with explicit abstention reason/category and safe request ID. | Record only the approved abstention provenance; create no candidate/assertion. |
| `cancelled` | Explicit user action; client may stop rendering/awaiting the operation. | No implicit retry or fallback. |
| `stale` | Typed response or problem indicating revision/freshness mismatch. | Do not silently overwrite or downgrade to an older project/graph state. |
| `error` | Finite non-2xx problem with stable code and request ID. | No semantic mutation; rollback/transaction boundary applies. |

An empty result is valid only when all of the following are true:

1. The operation completed at every required dependency boundary.
2. The response passed the versioned typed contract.
3. The authorization/project scope was established and revalidated.
4. The operation's domain definition permits zero records.
5. The terminal event records `success` or `abstained`, not `error`.

## Failure invariants

- No dependency failure becomes `200`, `201`, `[]`, `{}`, `null`, or a generic
  `unavailable` value unless that exact value is the documented domain result.
- No failed write leaves a partial Note, candidate, assertion, provenance
  record, or cross-project projection visible.
- No live provider failure changes provider, model, endpoint, prompt mode, or
  replay mode.
- No retry occurs unless the operation's reviewed retry policy authorizes it;
  every attempt is observable and bounded.
- No user-facing error contains secrets, provider payloads, prompts/source
  text, SPARQL/RDF, graph IRIs, stack traces, or other-project identifiers.
- Liveness and readiness remain separate. A live process is not evidence that
  its semantic dependencies are ready.
- A user-visible empty state must identify the collection/result and its
  freshness or abstention state; it must not be a generic failure placeholder.

## Required regression matrix

| Scenario | Expected public result | Expected mutation |
| --- | --- | --- |
| Authorized catalog has zero projects | Typed `200` empty catalog | None. |
| Graph projection has zero authorized nodes | Typed `200` empty projection with freshness | None. |
| Extraction has insufficient evidence | Typed successful abstention | Safe activity only; no candidate. |
| Provider timeout | Finite `503` problem, normalized timeout class | None. |
| Provider malformed JSON/schema | Finite `503` problem, schema class | None. |
| Semantic Core returns invalid JSON with `2xx` | Client/API contract failure, not success | None. |
| Fuseki unavailable during read | Finite non-2xx Core/API problem | None. |
| Fuseki failure during write | Finite non-2xx problem | Transaction rollback. |
| Stale project selection | Finite stale/forbidden/not-found problem | No scope change; no fallback project. |
| Explicit user retry | New visible attempt with same safe operation semantics | Idempotency/revision rules apply. |
| Live failure while replay is configured elsewhere | Live failure remains visible | Replay is not activated. |

## Review status and next dependencies

S8-03 owns the stable error codes/status mapping. S8-04 owns the shared event
schema and denylist. S8-05 owns the interactive retry decision. S8-06 owns
server-authorized project selection. S8-10 packages this contract for G1
approval. Until G1 is approved, this document remains `PROPOSAL_ONLY`.
