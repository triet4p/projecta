# Correlated Logging Contract — Sprint 8

**Status:** `PROPOSAL_ONLY` — pending S8-11 architecture/security approval
**Task:** S8-04
**Scope:** Browser boundary, Nginx, Application API, Semantic Core, Fuseki
gateway, provider attempts, operational audit, and Compose readiness

## Purpose

Every user-visible operation must be traceable from the same-origin boundary to
its terminal result without logging secrets, prompts, source text, provider
payloads, SPARQL/RDF, graph IRIs, or stack traces. This contract generalizes
the existing extraction telemetry and configuration audit fields into one
allowlisted event shape.

The contract distinguishes:

- `requestId`: canonical correlation identity for the inbound request and
  response;
- `operationId`: stable identity for one domain operation, including bounded
  downstream calls and explicit attempts;
- `attempt`: one-based attempt number within the operation; it remains `1` for
  the default interactive path;
- `terminalOutcome`: the same finite outcome used by the S8-03 taxonomy.

The first trusted server boundary owns the canonical IDs. A browser-supplied
ID may be accepted only as a bounded diagnostic hint and must never become a
trusted actor, project, graph, or storage identity.

## Canonical event schema

All services emit JSON structured events to stdout/stderr or the configured
event sink. Unknown fields are rejected by event builders in application code;
infrastructure may add transport metadata outside the application event.

```json
{
  "schemaVersion": "s8.logging.v1",
  "event": "operation.completed",
  "timestamp": "2026-08-09T12:00:00.123Z",
  "severity": "INFO",
  "service": "application-api",
  "boundary": "application",
  "requestId": "req-safe-opaque",
  "operationId": "op-safe-opaque",
  "scope": "project-scope-token",
  "routeClass": "quick-note.extract",
  "operation": "extract",
  "attempt": 1,
  "latencyMs": 842,
  "httpStatus": 200,
  "upstreamStatus": 200,
  "errorClass": null,
  "retryable": false,
  "terminalOutcome": "success",
  "resultCardinality": 2,
  "profileRevision": 4
}
```

### Required fields

| Field | Type/range | Rule |
| --- | --- | --- |
| `schemaVersion` | bounded string | Must be `s8.logging.v1` until a reviewed schema revision. |
| `event` | allowlisted string | One event name from the event vocabulary below. |
| `timestamp` | UTC RFC 3339 | Emitted at the boundary where the event occurred. |
| `severity` | `DEBUG`, `INFO`, `WARN`, `ERROR` | `ERROR` means terminal failure or failed health; not merely a provider HTTP status. |
| `service` | allowlisted service name | `web`, `nginx`, `application-api`, `semantic-core`, `fuseki-gateway`, `provider-adapter`, or `compose`. |
| `boundary` | allowlisted boundary | `browser`, `proxy`, `application`, `semantic-core`, `fuseki`, `provider`, `health`, or `audit`. |
| `requestId` | bounded opaque string | Canonical request correlation identity; required for request-scoped events. |
| `operationId` | bounded opaque string | Required for operation/dependency/provider events; may equal `requestId` for one-step calls. |
| `scope` | safe scope token or `none` | Project-safe, non-secret, non-graph-IRI scope; never raw trusted headers. |
| `operation` | allowlisted string | Domain operation such as `project.catalog`, `graph.expand`, `note.create`, `extract`, or `health.ready`. |
| `attempt` | integer `>= 1` | One-based attempt; no hidden increments. |
| `latencyMs` | integer `>= 0` or null | Duration from event boundary start to outcome. |
| `httpStatus` | integer or null | Public/local status at this boundary. |
| `upstreamStatus` | integer or null | Downstream status only when safe and available. |
| `errorClass` | S8-03 internal class or null | Required on failed terminal events; never raw exception text. |
| `retryable` | boolean | Derived from approved policy, not from arbitrary provider payload. |
| `terminalOutcome` | S8-03 outcome or null | Required on terminal events; omitted only for start/progress events. |

### Conditional fields

| Field | When allowed | Redaction rule |
| --- | --- | --- |
| `routeClass` | HTTP/proxy/application events | Finite route class, never query/body/path with IDs. |
| `dependency` | Dependency start/outcome | Allowlisted service name only. |
| `resultCardinality` | Successful finite reads/queries | Count only; never serialize rows, labels, IRIs, or source text. |
| `profileRevision` | LLM/configuration operation | Numeric revision only; never secret reference or credential. |
| `modelVersion` / `promptVersion` / `schemaVersion` | Provider/extraction event | Version identifiers only; no prompts or output. |
| `reasonCode` | Health/configuration/user-safe outcome | Must be from an allowlist; no exception detail. |
| `replayed` | Idempotent operation outcome | Boolean only; explicit replay mode remains visible. |
| `upstreamAddress` | Nginx/Fuseki diagnostics | Service name or approved host identity, never credentials/path/query. |

## Event vocabulary

| Event | Producer(s) | Required terminal fields |
| --- | --- | --- |
| `request.started` | Nginx, Application API | IDs, route class, scope, operation, attempt `1`. |
| `boundary.rejected` | Nginx, API, Core | IDs, error class, status, outcome `rejected`/`blocked`. |
| `dependency.started` | API, Core, Fuseki gateway | Dependency, IDs, operation, attempt. |
| `dependency.completed` | API, Core, Fuseki gateway | Status, latency, outcome, error class if failed. |
| `provider.attempt.started` | Provider adapter | Profile/model version, configured timeout, attempt; no payload. |
| `provider.attempt.completed` | Provider adapter | Status/class, latency, usage counters if available, outcome. |
| `operation.completed` | API, Core | Status, latency, outcome, result cardinality if applicable. |
| `operation.failed` | API, Core | Status/class, latency, retryability, outcome, rollback status if applicable. |
| `audit.recorded` | API/configuration/semantic lifecycle | Operation, actor-safe scope, outcome, revision metadata. |
| `health.probe` | Compose, API, Core | Dependency, probe kind, status, exit evidence, outcome. |

## Propagation contract

```text
Browser
  → Nginx same-origin boundary
  → Application API
  → Semantic Core
  → Fuseki gateway / provider adapter
  → Application API response
  → Browser result/error
```

Rules at each hop:

1. The first trusted boundary creates or validates the canonical
   `requestId`/`operationId`; malformed IDs are rejected or replaced according
   to the approved boundary policy, never logged raw.
2. Nginx forwards the canonical request ID and route class but strips body,
   credential, trusted project/actor, and arbitrary graph/query metadata from
   logs.
3. Application API forwards the same IDs to Semantic Core and provider/Fuseki
   adapters, along with only server-established project scope.
4. Semantic Core forwards the same IDs to Fuseki and records operation kind,
   project-safe scope, and terminal outcome.
5. A provider retry, if an approved mode permits one, increments `attempt` and
   emits a start/terminal pair for every attempt under the same operation ID.
6. The public response and final terminal event use the same request ID and
   terminal outcome. A missing response ID is a client contract failure.
7. Correlation IDs are not authorization. Project/actor scope is independently
   validated at every domain boundary.

## Scope and actor safety

`scope` is an internal safe token derived from the authorized project scope.
It may be a stable redacted token or an approved project-safe label, but it
must not be:

- a graph IRI, TDB2 path, secret, context secret, or authorization header;
- a raw browser-supplied project/actor value before server validation;
- a source text fragment or provider entity ID;
- a value that makes an unauthorized project discoverable through a 403/404
  distinction unless the public authorization contract permits it.

Actor identity may be recorded only in an approved audit field as a safe
server-established actor token. It is never taken from a browser body or
provider payload.

## Redaction denylist

Structured event builders must reject or omit:

- credentials, API keys, authorization headers, context secrets, secret
  references, cookies, and signed tokens;
- raw request/response bodies, prompts, note/source text, evidence text, and
  provider payloads;
- SPARQL, RDF/Turtle, graph IRIs, TDB2 paths, SQL, arbitrary query/filter text;
- stack traces, raw exception messages, memory addresses, file paths, and
  internal database keys;
- unbounded URLs, query strings, request headers, and cross-project IDs.

Redaction is a denylist safety layer, not the primary contract. Event builders
must construct events only from the allowlisted fields above.

## Operational guarantees

- Every request-scoped terminal operation emits exactly one terminal event at
  each applicable boundary; retries add attempt events but do not create extra
  operation terminal outcomes.
- The application event must be emitted before returning the public response;
  if durable audit persistence fails, the operation follows the S8-03 failure
  taxonomy instead of claiming successful audit.
- Event emission must not mutate semantic graphs or trigger retry/fallback.
- Logging failure must not expose payloads or block a safe error response; the
  service records a bounded internal logging failure metric/event when its
  platform supports it.
- Health events distinguish `live`, `ready`, and `not_ready`; a process cannot
  emit `ready` from a failed dependency probe.

## Regression requirements

1. Contract-test each event name for required fields, allowed values, and no
   forbidden fields.
2. Inject provider timeout/rate-limit/schema failure, Core 4xx/5xx, Fuseki
   outage/invalid response, Nginx timeout, stale project selection, and SHACL
   rollback; assert the same request/operation IDs across every emitted event.
3. Assert one terminal outcome per operation and one provider start/terminal
   pair per attempt.
4. Scan logs, traces, browser storage, DOM, and response bodies for secrets,
   provider payloads, prompts/source text, graph IRIs, and trusted headers.
5. Verify Nginx access/error events include route class, upstream result,
   latency, and connection outcome without request bodies.

## Existing implementation alignment

The current repository already has partial implementations: extraction
telemetry in `apps/api/src/projecta_api/extraction/telemetry.py`, configuration
audit in `apps/api/src/projecta_api/configuration/audit.py`, request IDs in the
Application API/Semantic Core contracts, and Nginx request forwarding. S8-04
does not treat those partial shapes as the complete Sprint 8 schema; S8-17 to
S8-22 must converge them on this proposal after G1.
