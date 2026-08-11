# Canonical Event Contract — Sprint 10

**Status:** `G1_APPROVED_IMPLEMENTATION`

**Task:** S10-03

**Contract version:** `canonical-event.v1`

## Boundary

A canonical event is the validated boundary between a provider-neutral
connector adapter and Projecta's ingestion orchestration. It identifies one
source occurrence and points to bounded evidence; it does not contain a domain assertion
and does not authorize a semantic mutation.

The adapter may propose source-system metadata, an external reference, an
actor hint, and an opaque cursor. The server derives project and installation
scope, validates every field, stores evidence through the approved evidence
port, and only then allows inbox claim and Semantic Core mapping.

The browser never submits or receives the internal canonical envelope. Public
API DTOs use safe opaque handles and projections.

## Canonical envelope

The internal envelope contains only this allowlisted structure:

```json
{
  "schemaVersion": "canonical-event.v1",
  "eventId": "evt-001",
  "connectorType": "json-mock",
  "eventType": "source.created",
  "projectScope": "server-derived-project-id",
  "installationScope": "server-derived-installation-id",
  "externalReference": "fixture://project-a/message-001",
  "actorHint": {
    "sourceSystem": "json-mock",
    "externalId": "fixture-user-001",
    "displayLabel": "Fixture user"
  },
  "occurredAt": "2026-08-10T09:00:00Z",
  "content": {
    "contentRef": "opaque-evidence-reference",
    "contentHash": "sha256:...",
    "contentType": "application/json",
    "byteLength": 287
  },
  "canonicalBodyHash": "sha256:..."
}
```

`projectScope` and `installationScope` are server-derived values in the
internal envelope. Adapter-supplied project hints are not trusted and are
either ignored or rejected on mismatch. `contentRef` is an opaque evidence
store reference and is not part of the stable content identity because the
storage locator may change during backup/restore.

No additional free-form metadata field is allowed in v1. Provider-specific
fields must remain in raw evidence and require a future reviewed contract
extension.

## Field contract

| Field | Required | Contract |
| --- | --- | --- |
| `schemaVersion` | Yes | Exactly `canonical-event.v1`; unknown versions fail closed. |
| `eventId` | Yes | Stable adapter identity, 1–128 ASCII characters, URL-safe opaque format; unique within an installation. |
| `connectorType` | Yes | Finite allowlisted type, 1–64 characters; must match the selected installation. |
| `eventType` | Yes | Finite allowlisted source event type, 1–64 characters; v1 enables `source.created` and `source.updated` only. |
| `projectScope` | Yes | Server-derived internal project binding; never trusted from adapter/browser input. |
| `installationScope` | Yes | Server-derived internal installation binding; must be enabled and belong to `projectScope`. |
| `externalReference` | Yes | Opaque source-resource reference, 1–512 Unicode scalar values; path traversal and control characters are rejected. |
| `actorHint` | No | Non-authoritative source hint with bounded source system, external ID, and display label; never an authenticated principal or automatic identity merge. |
| `occurredAt` | Yes | RFC 3339 timestamp normalized to UTC; must be within the accepted event-age/future-skew window. |
| `content.contentRef` | Yes | Opaque reference returned by the evidence port; no filesystem path, object-store key, or provider URL is exposed. |
| `content.contentHash` | Yes | Lowercase SHA-256 digest of the stored evidence bytes, formatted `sha256:<64 hex characters>`. |
| `content.contentType` | Yes | Adapter capability allowlist; v1 permits `application/json` and `text/plain` only. |
| `content.byteLength` | Yes | Exact evidence byte length, non-negative, and within the configured per-event limit. |
| `canonicalBodyHash` | Yes | SHA-256 of the canonical body described below; used for replay/conflict detection. |

The envelope contains no Requirement, Task, relation, assertion status, RDF
IRI, graph name, semantic class, semantic predicate, secret, credential,
trusted actor, raw payload, or provider-shaped object.

## Stable event identity and idempotency

The operational event key is derived from the server-bound tuple:

```text
(projectScope, installationScope, connectorType, eventId)
```

The tuple is stored as an internal idempotency identity. It is not returned as
a public identifier. The first accepted event records its canonical body hash
and terminal outcome. A later submission with the same identity behaves as
follows:

- The same `canonicalBodyHash` returns the original committed outcome as a
  replay and performs no second source/evidence/candidate mutation.
- A different `canonicalBodyHash` returns `EVENT_BODY_CONFLICT`; it never
  overwrites the original body or advances the cursor.
- A duplicate presented concurrently has one winning claim. Losers observe
  the committed result or a typed conflict after the winner completes.

The event key is scoped to the installation and project so the same adapter
event ID may exist in two authorized installations without cross-project
collision.

## Canonical serialization and hashing

The canonical body is the UTF-8 deterministic JSON serialization of these
fields in the envelope:

```text
schemaVersion
eventId
connectorType
eventType
projectScope
installationScope
externalReference
actorHint
occurredAt
content.contentHash
content.contentType
content.byteLength
```

Serialization rules:

- Object keys are sorted lexicographically at every level.
- No insignificant whitespace is emitted.
- Strings are valid UTF-8 and use one normalized representation before hashing.
- Timestamps are normalized to UTC with a canonical `Z` representation.
- Integers are emitted as decimal integers without leading zeroes; floating
  point values are not permitted in the envelope.
- Duplicate object keys, non-finite numbers, control characters, and unknown
  fields fail validation.
- `contentRef`, request/correlation IDs, received time, cursor, retry metadata,
  and storage paths are excluded because they are operational locators/state,
  not event content identity.

`canonicalBodyHash` is `SHA-256(canonicalBodyBytes)`. The evidence
`contentHash` is `SHA-256(rawEvidenceBytes)` and must be verified before the
event can be claimed. The two hashes serve different purposes and must not be
substituted for one another.

## Bounds

The following v1 defaults are proposed for G1 approval and may be tightened by
configuration, never widened by an adapter or browser request:

| Boundary | Limit |
| --- | ---: |
| Events per sync run | 100 |
| Total evidence bytes per run | 10 MiB |
| Evidence bytes per event | 1 MiB |
| Maximum JSON nesting depth | 16 |
| Maximum object/array fields per resource | 128 |
| Maximum string length | 16 KiB |
| Maximum actor-hint fields | 3 |
| Maximum event envelope bytes | 64 KiB |
| Maximum external-reference length | 512 Unicode scalar values |
| Maximum event age | 365 days, subject to installation policy |
| Maximum future clock skew | 15 minutes |

The outer sync deadline is independent of these data limits. Reaching a limit
is a typed validation outcome, not an invitation to paginate, retry internally,
or process an unbounded remainder.

## Validation order

The ingestion boundary validates in this order:

1. Parse bounded bytes and reject malformed/duplicate-key JSON.
2. Validate schema version, field allowlist, field types, and string/structure
   bounds.
3. Resolve the server-owned installation and project binding; reject scope or
   capability mismatch before adapter/provider work continues.
4. Validate event identity, event type, external reference, actor hint, and
   normalized timestamp.
5. Validate evidence reference metadata, content type, byte count, and digest.
6. Recompute canonical serialization and both hashes.
7. Claim the event idempotently in the operational inbox.
8. Only after claim, allow evidence/source mapping and Semantic Core commit.

Validation failure before claim cannot create a semantic artifact or advance a
cursor. A post-claim terminal failure is recorded through the run/dead-letter
contract and remains replayable according to the original outcome.

## Typed validation problems

The allowlisted error codes are:

- `EVENT_SCHEMA_UNSUPPORTED`
- `EVENT_FIELD_UNKNOWN`
- `EVENT_FIELD_MISSING`
- `EVENT_FIELD_TYPE_INVALID`
- `EVENT_ID_INVALID`
- `EVENT_TYPE_UNSUPPORTED`
- `EVENT_SCOPE_MISMATCH`
- `EVENT_INSTALLATION_MISMATCH`
- `EVENT_CAPABILITY_UNSUPPORTED`
- `EVENT_EXTERNAL_REFERENCE_INVALID`
- `EVENT_ACTOR_HINT_INVALID`
- `EVENT_TIMESTAMP_INVALID`
- `EVENT_TIMESTAMP_OUT_OF_WINDOW`
- `EVENT_CONTENT_REFERENCE_INVALID`
- `EVENT_CONTENT_TYPE_UNSUPPORTED`
- `EVENT_CONTENT_SIZE_EXCEEDED`
- `EVENT_CONTENT_HASH_INVALID`
- `EVENT_CANONICALIZATION_FAILED`
- `EVENT_BODY_CONFLICT`
- `EVENT_IDEMPOTENCY_CONFLICT`
- `EVENT_LIMIT_EXCEEDED`

Each problem contains only a safe code, correlation ID, event/install opaque
handle when already authorized, bounded field name where safe, terminal/retry
classification, and timestamp. It never includes raw event content, secret
material, stack traces, SQL, RDF IRIs, graph names, filesystem paths, or a
cross-project resource existence signal.

## Semantic boundary

`eventType` describes source ingestion behavior only. It does not mean that a
Requirement, Task, relation, or other domain fact exists. Mapping to Note,
NoteItem, candidate, evidence, provenance, and later assertion is owned by the
released Semantic Core lifecycle and is specified separately in S10-39–43.

## Compatibility and unresolved decisions

- The contract is additive to the v0.4.0 Application API and does not change
  released routes.
- Operational event state remains outside RDF and outside the ontology.
- The initial JSON/Mock event-type allowlist and numeric bounds require G1
  approval before implementation.
- If implementation requires a new domain term rather than operational/event
  metadata, S10-09 must classify it and the ontology governance gate applies.
