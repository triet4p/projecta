# JSON/Mock Connector Vertical-Slice Use Case — Sprint 10

**Status:** `G1_APPROVED_IMPLEMENTATION`

**Task:** S10-02

**Purpose:** Define the deterministic, server-authorized connector journey that
Sprint 10 must implement and validate before any live external provider is
considered.

## Product boundary

The JSON/Mock adapter is a deterministic inbound connector. It reads a bounded
fixture/resource set from the approved local boundary, emits canonical events,
and returns an opaque cursor. It does not call the network, resolve external
identities into asserted people, invoke Semantic Core, or perform semantic
mutation itself.

The application server owns actor, project, installation, capability, policy,
deadline, idempotency, evidence, and Semantic Core decisions. The browser is a
typed client only and never becomes an authority by selecting a project/actor,
connector, credential, raw payload, RDF identifier, or storage path.

## Actors

| Actor | Responsibility | Authority boundary |
| --- | --- | --- |
| Connector administrator | Installs, enables, disables, runs, inspects, or explicitly retries a connector for an allowed project | Must be resolved by the server-owned principal and policy layer |
| Project member | Reads allowed installation/run/projection state | Cannot install, run, retry, or inspect another project by guessing handles |
| Application API | Authenticates the request context, evaluates policy, orchestrates one bounded attempt, and projects safe results | Browser input is untrusted; all scope and capabilities are revalidated |
| JSON/Mock adapter | Reads the approved bounded fixture and emits canonical events/cursor evidence | No network, credential, direct RDF, or semantic mutation |
| Operational store | Persists installations, inbox/idempotency, runs, cursors, retries, dead letters, and audit metadata | PostgreSQL operational state; never semantic RDF truth |
| Evidence store | Persists bounded immutable/content-addressed source bytes | Raw payload is evidence, not domain truth, and is never sent to the browser |
| Semantic Core | Maps approved source content through Note/NoteItem, SHACL, provenance, candidates, and existing Graph/Review Queue lifecycle | Only the existing review boundary can produce assertions |
| Human reviewer | Reviews candidates and may confirm/reject them through the released workflow | Connector import never bypasses this responsibility |

## Preconditions

Before a run can start:

- A server-owned principal exists with membership in the target project and the
  connector-admin permission required for the requested operation.
- The connector type is present in the finite allowlist and declares inbound
  import capability.
- A project-scoped installation exists, is enabled, and has a current revision.
- The fixture/resource reference is within the approved local boundary and is
  bounded by the configured byte, event-count, field-count, and time budgets.
- The request carries a new operation idempotency key or an explicitly
  authorized replay/retry command with the required revision linkage.
- The application has a correlation identifier and one absolute deadline for
  the entire operation.
- Semantic Core, operational storage, and evidence storage are reachable and
  use the same project scope. A failure must produce a terminal result rather
  than a partial success.

## Primary journey: authorized import

1. The connector administrator opens the project-scoped Connections surface.
2. The server returns the finite JSON/Mock catalog and safe capabilities.
3. The administrator creates an installation with the approved fixture
   reference and receives an opaque, revision-bound installation handle.
4. The administrator enables the installation after the server rechecks policy,
   capability, project membership, and revision.
5. The administrator requests one explicit sync with a new idempotency key.
6. The API creates exactly one sync run, calls the adapter once, validates and
   claims each canonical event, stores bounded evidence, and commits source
   artifacts through Semantic Core.
7. The API returns one correlated terminal result with safe counts and a
   truthful state such as `succeeded`, `replayed`, `failed`, or `cancelled`.
8. The UI shows the installation, last run, cursor summary, and dead-letter
   summary without exposing raw payload, secret, RDF, SQL, or provider IDs.

Expected user-visible success:

- The run reaches exactly one terminal state.
- The imported content is visible as project-scoped source Note/NoteItem data.
- Reviewable candidates and evidence/provenance links are visible in the
  existing Graph and Review Queue projections.
- No content is shown as an asserted Requirement, Task, relation, or inferred
  fact before the existing review lifecycle confirms it.

## Seven acceptance journeys

### 1. Authorized import

An authorized connector administrator installs and runs the JSON/Mock connector
for one project with a valid bounded fixture. The user sees one truthful,
correlated terminal result and the expected safe run summary.

### 2. Evidence lifecycle

Imported content is stored as bounded evidence, mapped to a source Note and
NoteItems, and produces reviewable candidates with exact source offsets,
content hash, and provenance. Graph and Review Queue show the imported source
without automatic assertion.

### 3. Idempotent replay

The identical event identity and canonical body are submitted again. The
system returns the original successful outcome, does not create another source
artifact/candidate set, advances the cursor only once, and marks the operation
as a replay.

### 4. Isolation

A forged, stale, disabled, invisible, or cross-project installation/event
handle is rejected with a finite safe problem. The response does not confirm
whether another project has a matching installation, event, secret, evidence,
cursor, or run.

### 5. Failure truthfulness

Malformed fixture data, unsupported capability, unavailable storage, semantic
rejection, timeout, and interrupted execution each produce a bounded,
correlated terminal outcome. No partial semantic write remains and the cursor
does not advance on failure.

### 6. Recovery

Installation, inbox, run, cursor, dead-letter, and evidence state survive an
API/PostgreSQL restart. After isolated backup/restore, replaying the last event
returns the original outcome and creates no duplicate source, candidate,
assertion, run outcome, or cursor advancement.

### 7. Accessible operation

The Connections screen exposes installation, capability, last success, active
run, replay/failure, and recovery state through keyboard-accessible controls,
focus management, live announcements, narrow-layout support, and a first-class
table/list representation that does not depend on color or a visual graph.

## Bounded fixture and resource shape

The fixture is a local test resource, not a public API payload and not a
provider-shaped contract. The final field names and limits are defined by
S10-03; this example only fixes the use-case boundary.

```json
{
  "fixtureVersion": "json-mock.v1",
  "connectorType": "json-mock",
  "resources": [
    {
      "externalReference": "fixture://project-a/message-001",
      "occurredAt": "2026-08-10T09:00:00Z",
      "eventType": "source.created",
      "actorHint": "fixture-user-001",
      "contentType": "application/json",
      "content": {
        "title": "Payment dashboard refresh",
        "items": [
          {
            "type": "requirement",
            "text": "The dashboard should refresh every 30 minutes."
          },
          {
            "type": "question",
            "text": "Confirm the retention period before implementation."
          }
        ]
      }
    }
  ]
}
```

The fixture must be constrained by explicit limits for total bytes, resource
count, event count, nesting depth, string length, item count, content type,
timestamp range, and canonical serialization size. A fixture exceeding a limit
is rejected before inbox claim or semantic mutation.

## Counterexamples and required outcomes

| Counterexample | Required outcome |
| --- | --- |
| Browser supplies a different project or actor than server context | Ignore/reject the forged value; do not widen scope |
| Installation belongs to another project | Safe not-found/forbidden mapping with no existence leak |
| Disabled installation is run | Reject without adapter call or cursor movement |
| Unknown connector type or capability | Typed unsupported operation; no provider import or arbitrary execution |
| Same event identity with a different canonical body | Typed conflict; preserve the original committed outcome |
| Oversized, malformed, deeply nested, or path-like fixture | Validation failure/dead letter; no raw payload persistence beyond approved safe handling |
| Evidence write succeeds but Semantic Core commit fails | Terminal failure; transaction/cursor semantics prevent a partial semantic write |
| Semantic Core commit succeeds but cursor commit races | One winner; cursor advances at most once and replay returns the committed result |
| Request deadline expires or process is interrupted | Cancelled/failed terminal state; no hidden retry and no cursor advance |
| Retry is requested without authorization, expected revision, or new key | Reject before adapter execution |
| External identity matches only by display name | Keep as a hint/candidate; never merge identities automatically |

## User-visible outcome contract

Every operation has one correlated terminal outcome from a finite allowlist:

- `pending` while the bounded operation is still active;
- `succeeded` when source/evidence and semantic commit complete;
- `replayed` when the canonical event already has a committed outcome;
- `failed` for a terminal adapter, storage, validation, or Semantic Core error;
- `cancelled` when the explicit deadline/cancellation ends the run;
- `disabled` or `forbidden` when policy prevents execution;
- `retry-conflict` when the retry revision or idempotency contract is invalid.

Public responses contain correlation, safe counts, opaque handles, bounded
status, and redacted error details only. They do not contain raw event bodies,
credentials, internal IDs, SQL/storage details, RDF IRIs, graph names, stack
traces, or provider-shaped objects.

## Explicit non-goals

Sprint 10 does not implement or claim:

- Teams, Outlook, Jira, Slack, webhook delivery, polling, OAuth consent, or a
  live external-provider connector.
- Outbound messages, replies, task creation, uploads, or other external side
  effects.
- Production authentication, tenant administration, production RBAC/ABAC, or
  production secret-manager integration.
- Automatic identity merge or direct assertion from imported content.
- Arbitrary connector execution, filesystem paths, object-store keys, SQL,
  SPARQL, RDF graphs, external resource IDs, or raw provider payloads.
- A new connector-specific Requirement/Task ontology vocabulary.

## Review boundary

This use case was approved with the complete architecture, security, semantic,
persistence, evidence, and runtime boundaries at S10-10 on 2026-08-10.
