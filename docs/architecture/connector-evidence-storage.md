# Connector Evidence Storage Contract — Sprint 10

**Status:** `G1_APPROVED_IMPLEMENTATION`

**Task:** S10-08

**Contract version:** `connector-evidence.v1`

## Boundary

Evidence storage preserves bounded raw connector content for provenance,
reprocessing, validation, and recovery. Evidence is source memory, not domain
truth. The Application API and browser receive only safe metadata or opaque
evidence-link handles; they never receive raw payloads, arbitrary object keys,
filesystem paths, or provider storage URLs.

PostgreSQL stores the evidence reference, digest, bounded metadata, retention
state, and project-scoped linkage. The object/evidence adapter stores the raw
bytes. RDF stores source metadata and provenance through Semantic Core, not the
raw connector body.

## Port

The provider-neutral evidence port is:

```python
class EvidenceStore(Protocol):
    async def put(
        self,
        request: EvidencePutRequest,
        *,
        deadline: AbsoluteDeadline,
        cancellation: CancellationToken,
    ) -> EvidenceReceipt: ...

    async def get(
        self,
        request: EvidenceGetRequest,
        *,
        max_bytes: int,
        deadline: AbsoluteDeadline,
        cancellation: CancellationToken,
    ) -> EvidenceStream: ...

    async def head(
        self,
        request: EvidenceHeadRequest,
        *,
        deadline: AbsoluteDeadline,
    ) -> EvidenceMetadata: ...

    async def mark_for_retention_purge(
        self,
        request: EvidenceRetentionRequest,
        *,
        deadline: AbsoluteDeadline,
    ) -> RetentionDecision: ...
```

There is no `list_all`, arbitrary-path read, arbitrary-key write, public URL
generation, or browser-selected delete operation. The application owns project
authorization and lifecycle decisions before invoking the port.

## Evidence object and metadata

An evidence object is identified internally by:

```text
(project_scope, content_hash, evidence_version)
```

The public reference is opaque and revision/authorization bound. Physical
storage keys are implementation details and never appear in API responses,
logs, telemetry, RDF, or dead letters.

Required metadata:

- server-issued opaque evidence reference;
- project scope and installation/event/run linkage;
- lowercase SHA-256 content digest;
- exact raw byte length;
- allowlisted content type;
- immutable creation timestamp;
- retention class and retention-until timestamp;
- immutable/content-addressed state;
- evidence contract version;
- safe correlation and source provenance reference.

Forbidden metadata/content exposure:

- raw credentials, authorization headers, or secret values;
- arbitrary provider payload fields in public metadata;
- filesystem paths, object-store keys, bucket names, SQL, RDF IRIs, graph
  names, stack traces, or provider SDK objects;
- an unbounded preview/snippet returned to the browser;
- an external URL that bypasses the Application API authorization boundary.

## Immutable/content-addressed write

`put` writes through a bounded stream and computes the digest from the exact
bytes received. It must:

1. validate server project/installation/event scope;
2. validate content type and declared/observed size against limits;
3. stream bytes without loading an unbounded object into memory;
4. compute `SHA-256(rawEvidenceBytes)` while writing a temporary object;
5. reject if declared digest, observed digest, or byte length differs;
6. atomically publish the content-addressed object and metadata;
7. return an opaque reference and safe receipt.

For an existing `(project, contentHash, version)` object:

- identical bytes return the existing immutable receipt and are idempotent;
- different bytes cannot reuse the same digest and fail closed;
- metadata may only receive an allowed retention/linkage update through an
  authorized revision, never overwrite the immutable content facts.

An interrupted write leaves no visible complete object. Temporary files are
private to the adapter, bounded, and cleaned up by safe recovery; their paths
are not returned or logged.

## Allowlist and limits

The v1 JSON/Mock evidence allowlist is:

| Content type | Purpose | v1 status |
| --- | --- | --- |
| `application/json` | Canonical JSON/Mock fixture/resource bytes | Allowed |
| `text/plain` | Bounded source text resource | Allowed |
| Any other media type | Binary/provider-specific content | Rejected until reviewed |

Proposed defaults require G1 approval:

| Limit | Default |
| --- | ---: |
| Bytes per evidence object | 1 MiB |
| Total evidence bytes per sync run | 10 MiB |
| Evidence objects per sync run | 100 |
| Maximum metadata fields | 32 |
| Maximum metadata string length | 512 characters |
| Maximum retention horizon | Installation/project policy bound |
| Read response bytes | Caller-supplied finite limit, never above object size/policy |

Compression, decompression, archives, recursive containers, executable media,
and format sniffing that can expand beyond the configured bound are not part of
v1. If a future adapter needs them, expansion limits and bomb tests require a
separate reviewed contract change.

## Bounded reads

`get` and `head` require:

- an authorized project-scoped opaque evidence reference;
- an expected evidence/project/revision binding where applicable;
- a finite maximum byte limit;
- one absolute deadline and cancellation token;
- a purpose/operation correlation for audit.

`get` returns a bounded stream with an observed digest/length check. It stops
before the limit and returns a typed bounded-read error rather than truncating
silently. It never supports range/path traversal or list-all semantics unless a
future reviewed contract adds a finite, typed range operation.

Missing, invisible, expired, or cross-project references use the safe
not-found/forbidden policy without revealing whether another project has the
object. A public API does not return raw source text as an error fallback.

## Project isolation

Evidence access is authorized twice:

1. The Application API/policy layer resolves principal, project, installation,
   event, and allowed operation.
2. The evidence adapter verifies the internal project scope and reference
   binding before read/write/retention work.

Physical content-addressing must not accidentally make equal bytes globally
   readable. Deduplication, if used, is behind the project authorization layer
   and does not share a public reference across projects.

Raw evidence is not copied into RDF or operational rows. Semantic Core receives
only the approved source content/metadata through its typed ingestion boundary,
with source offsets, hash, project context, and provenance preserved.

## Retention and safe deletion

Retention is server-authorized and audit-recorded. Browser/UI code cannot delete
an object by reference. A retention worker may:

1. mark an object eligible after its retention-until time;
2. verify no active source/provenance/recovery/retry policy requires it;
3. record the decision and evidence revision;
4. purge the physical bytes through the adapter;
5. retain a sanitized tombstone/metadata record where audit policy requires.

Deletion must not erase semantic provenance, rewrite asserted knowledge, or make
a committed run appear never to have happened. If evidence is still required
for review, replay, legal retention, or restore verification, deletion is
blocked or deferred. Any failed purge remains an explicit operational state,
not a successful deletion.

## Error contract

Evidence errors are finite and sanitized:

- `EVIDENCE_PROJECT_FORBIDDEN`
- `EVIDENCE_NOT_FOUND`
- `EVIDENCE_REFERENCE_INVALID`
- `EVIDENCE_CONTENT_TYPE_UNSUPPORTED`
- `EVIDENCE_SIZE_EXCEEDED`
- `EVIDENCE_METADATA_INVALID`
- `EVIDENCE_DIGEST_MISMATCH`
- `EVIDENCE_CONTENT_CONFLICT`
- `EVIDENCE_WRITE_INTERRUPTED`
- `EVIDENCE_READ_LIMIT_EXCEEDED`
- `EVIDENCE_RETENTION_BLOCKED`
- `EVIDENCE_RETENTION_FAILED`
- `EVIDENCE_UNAVAILABLE`
- `EVIDENCE_DEADLINE_EXCEEDED`
- `EVIDENCE_CANCELLED`

Errors contain only code, correlation, safe bounded field/class, terminal or
retry classification, and timestamp. They never include raw bytes, content
snippets, credentials, storage paths/keys, SQL, RDF, stack traces, or another
project's identifiers.

## Restart, backup, and restore

The local/Compose adapter uses a dedicated persistent evidence volume and the
same port that a future S3-compatible adapter must implement. Restart must
preserve immutable objects and metadata. Backup must capture a consistent view
of bytes plus metadata/references, and restore must verify:

- digest and byte length for each restored object;
- project/revision/linkage scope;
- retention metadata and tombstone state;
- compatibility with PostgreSQL event inbox/run records;
- replay-after-restore creates no duplicate source, candidate, assertion, or
  cursor advancement.

Restore is validated only in an isolated clean stack. It must never mutate
shared or production data during a test.

## Required tests

The implementation must cover:

- valid put/get/head and same-content idempotency;
- digest mismatch and same-key/different-content conflict;
- oversize object, unsupported media, invalid metadata, malformed content;
- interrupted write, missing object, restart persistence, and bounded streaming;
- path traversal, arbitrary key/list-all attempts, cross-project reference,
  stale/invisible reference, and safe error mapping;
- retention blocked/failed/successful paths and sanitized audit/log output;
- backup/restore digest verification and replay-after-restore behavior;
- seeded secret/raw payload scans across API/web/DB/RDF/logs/telemetry.

## G1 decisions required

Human approval at S10-10 must confirm the evidence port, local/Compose adapter,
content/media/size limits, project isolation, retention/deletion policy,
backup/restore ownership, and the rule that raw evidence remains source memory
rather than domain assertion.
