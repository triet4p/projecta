# Connector Ingestion Threat Model — Sprint 10

**Status:** `G1_APPROVED_IMPLEMENTATION`

**Task:** S10-06

**Scope:** JSON/Mock inbound connector vertical slice and the provider-neutral
boundaries it establishes for future connectors.

## Security objective

Connector ingestion must be server-authorized, project-scoped, deterministic,
bounded, idempotent, fail-explicit, and incapable of turning untrusted source
content into asserted semantic truth. A malicious or malformed connector input
must not cause cross-project disclosure, arbitrary network/filesystem access,
secret leakage, unbounded work, partial semantic state, or hidden retry loops.

## Assets and security properties

| Asset | Required property |
| --- | --- |
| Server-owned principal and project scope | Authentic, non-forgeable at browser/adapter boundary, revalidated per operation |
| Installation and capability state | Project-scoped, revisioned, policy-controlled, auditable |
| Canonical event identity/body hash | Stable, collision-resilient for the bounded contract, conflict-safe |
| Raw evidence | Immutable/content-addressed, bounded, digest-verified, retention-aware, not public domain truth |
| Operational state | Transactional, project-predicated, replayable, no raw credentials/payloads |
| Cursor | Opaque, committed exactly once only after semantic success, unchanged on failure |
| Semantic source/candidate/asserted/inferred graphs | Correct lifecycle separation, provenance, same-project isolation |
| Secrets | Server-side opaque references only; plaintext never in browser, logs, RDF, or connector tables |
| Public API/UI projections | Typed, finite, truthful, opaque, no internal IDs/storage/provider payloads |
| Audit/telemetry | Correlated and safe, no raw payload, secret, stack trace, SQL, or RDF IRI |

## Trust zones and boundaries

```text
Z0 Browser / UI / user input (untrusted)
   │ typed API only; no trusted headers or raw IDs
Z1 Application API + server-owned principal/policy (trusted boundary)
   ├── Z2 Connector registry/adapter (provider code, constrained)
   ├── Z3 PostgreSQL operational state (trusted storage boundary)
   ├── Z4 Evidence object store (raw source bytes, bounded)
   └── Z5 Semantic Core → Fuseki/TDB2 (semantic transaction boundary)
```

The JSON/Mock fixture is treated as untrusted source content even when it is
read from a local test volume. A future provider network is an additional
untrusted boundary; a live provider cannot weaken these controls.

## Threats and controls

| ID | Threat/attack | Required control | Evidence expected |
| --- | --- | --- | --- |
| T01 | Forged project/actor/trusted headers | Strip browser headers at the server boundary; resolve principal/project from server state; reject missing/invalid context | API negative test and browser evidence showing forged values cannot change scope |
| T02 | Cross-project event replay | Bind installation/event identity to server project scope; project predicate on inbox/evidence/Core access; map invisible handle safely | Two-project replay test with no cross-project row, graph, count, log, or error disclosure |
| T03 | Confused deputy | Require operation-specific principal capability and membership immediately before adapter call; never let fixture/provider select project or actor | Policy matrix tests for catalog/read/install/run/retry and forged scope |
| T04 | SSRF or arbitrary network access | JSON/Mock has no network capability; adapter registry allowlist; future resource fetch uses approved provider port, host/policy allowlist, one deadline, no arbitrary URL | Static import-boundary test, runtime no-network test, rejected URL/path fixtures |
| T05 | Path traversal/local file read | Treat external references as opaque; reject path separators/traversal/device paths; evidence port has no arbitrary-path/list-all operation | `..`, absolute path, UNC/device, symlink, and cross-project reference tests |
| T06 | Payload bomb/resource exhaustion | Enforce byte/event/field/string/depth/time limits before claim and before parse expansion; no unbounded pagination/recursion | Oversize, deep nesting, huge string, many-event, and timeout tests |
| T07 | Malicious JSON | Reject malformed JSON, duplicate keys, unknown fields, invalid Unicode/numbers, unsafe content types, and canonicalization mismatch | Canonical parser/hash tests and malformed-fixture matrix |
| T08 | Secret leakage | Only opaque SecretStore references; no raw credentials in input tables, DTOs, logs, telemetry, RDF, evidence, or assets; JSON/Mock requires no credential | Seeded-secret scan across API/web/DB/RDF/logs/fixtures and negative response assertions |
| T09 | Raw payload/log injection | Store raw bytes only in bounded evidence; sanitize error/audit/telemetry fields; never echo source content or stack traces | Payload leak gate, log scan, safe-error tests |
| T10 | Cursor tampering or premature advance | Cursor is opaque and server-owned; compare expected revision; advance exactly once after source/evidence/Core commit; rollback on all failure classes | Concurrent cursor, failure-injection, restart, and replay tests |
| T11 | Duplicate delivery | Unique project/installation/event identity plus canonical body hash; first winner commits; same body replays; different body conflicts | Concurrent claim/replay/body-conflict tests |
| T12 | Partial commit | Use explicit operational/evidence/Semantic Core transaction/compensation boundary; cursor stays unchanged unless all required commits succeed; terminal result records failure | Storage/Core failure injection, rollback, no-partial-write assertions |
| T13 | Disabled-installation race | Recheck enabled state/revision before adapter call and during claim; disable wins or run has a recorded authorization snapshot; no new work after disable boundary | Disable-versus-run concurrency test and audit evidence |
| T14 | Retry amplification/hidden retries | One adapter call per run, one absolute deadline, no nested SDK/HTTP/proxy/worker retry; retry is a new authorized run/key/revision | Request-count, timeout, retry-lineage, and bounded-duration tests |
| T15 | Dead-letter data exfiltration | Store only allowlisted failure class/detail/correlation/handles/timestamps; never raw payload, secret, SQL, RDF, path, or stack trace | Dead-letter schema/scan and injected-exception redaction tests |
| T16 | Capability/type confusion | Registry resolves explicit unique allowlisted type; descriptor capability snapshot is revisioned; unknown/duplicate/provider-specific types fail closed | Registry tests for unknown/duplicate/mismatched capability |
| T17 | Identity merge by display name | Actor hints are non-authoritative; deterministic match may create a reviewable candidate only; human confirmation for ambiguity | Same-name multi-identity fixture and no-auto-merge assertion |
| T18 | Semantic assertion injection | Canonical event has no domain predicate/assertion; imported source maps only to Note/NoteItem/candidate through Semantic Core review lifecycle | RDF graph inspection and candidate/assertion separation tests |
| T19 | Evidence substitution/hash confusion | Verify raw-byte digest; keep evidence content hash distinct from canonical event body hash; content reference cannot redefine bytes | Digest mismatch, restore, and canonical hash tests |
| T20 | Timing/existence leak | Use safe stable mapping for invisible resources; avoid project/installation IDs in errors/logs; bound failure work and response shape | Cross-project status/body/timing/log assertions |

## Attack-path controls

### Forged scope and confused deputy

The browser can send arbitrary JSON, handles, headers, and idempotency keys.
The API strips or ignores trusted headers from the client, resolves a
server-owned principal, revalidates membership and installation ownership, and
passes only the authorized bounded context to the adapter. An adapter-supplied
project hint is untrusted. A forged or invisible handle follows the safe
403/404 policy and never selects another project's resources.

### SSRF, path traversal, and fixture escape

The JSON/Mock adapter has no network capability and reads only the approved
fixture/resource boundary. References are opaque and are not converted into
filesystem paths. The evidence port exposes bounded put/get by an internally
issued reference, not list-all, arbitrary path, recursive directory traversal,
or caller-chosen object-store key. Future adapters require an explicit reviewed
network/resource policy before implementation.

### Malicious input and payload bombs

Input size is bounded before parsing. The parser rejects duplicate keys,
unknown fields, unsafe numeric values, invalid content type, excessive nesting,
oversized strings, and count/byte limits. Canonicalization and digest checks
run before inbox claim. A limit failure is terminal for the bounded operation;
the system does not silently paginate, retry, or continue with an unbounded
remainder.

### Duplicate delivery, partial commit, and cursor races

The inbox identity is unique inside the server project/installation boundary.
A winning transaction records the body hash and outcome. A same-body replay
returns the original result; a different-body reuse conflicts. Evidence/source
and Semantic Core commit must succeed before cursor advancement. Any validation,
storage, timeout, cancellation, Core, dead-letter, or process failure leaves
the previous cursor and semantic state unchanged.

### Secret, log, and dead-letter leakage

Secrets are opaque references resolved only inside the server boundary. Error,
audit, telemetry, and dead-letter records use finite safe fields. Raw payloads,
credentials, internal identifiers, RDF/SQL/storage details, and stack traces
are scanned out of API responses, browser state/assets, databases, RDF, logs,
telemetry, and review artifacts.

## Security invariants

The implementation is not acceptable if any of these are false:

1. No browser or adapter input can change server-owned project/actor scope.
2. No operation can execute an unallowlisted connector/capability/provider.
3. No connector run can exceed its outer deadline, byte/count budget, or one
   adapter attempt.
4. No event identity can overwrite a different canonical body.
5. No cursor advances without the corresponding committed source/evidence and
   Semantic Core outcome.
6. No failure leaves a partial semantic write or a false successful result.
7. No raw secret/payload/internal storage/semantic identifier crosses a public
   response, browser state, log, telemetry, RDF, or dead-letter boundary.
8. No imported source becomes an assertion without the existing human-review
   lifecycle.
9. No cross-project existence or data is revealed through any response,
   projection, error, count, log, telemetry, timing, or retry behavior.
10. Local experience mode is never reported as production authentication.

## Required abuse/failure tests

The Sprint 10 test matrix must include:

- browser-forged trusted headers and project/actor bodies;
- invisible, stale, disabled, cross-project, and duplicate handles/events;
- duplicate keys, malformed JSON, invalid hashes, path traversal, URL-like
  references, deep nesting, oversized strings, and event-count/byte bombs;
- registry unknown/duplicate/capability mismatch;
- adapter timeout, cancellation, malformed output, unavailable dependency,
  process interruption, and no-hidden-retry request counts;
- PostgreSQL/evidence/Core partial failure and rollback;
- concurrent claim, replay, retry, disable-versus-run, cursor advancement,
  and two-project isolation;
- seeded credential/raw-payload leakage in responses, DOM/storage, assets,
  PostgreSQL safe columns, RDF, logs, telemetry, fixtures, and review packet.

## Residual risks and G1 decisions

The following risks remain open until G1:

- A production identity provider and tenant policy are not implemented.
- The first runtime placement (inside API or separate deployable) is not chosen.
- Exact network policy for future live adapters is intentionally absent.
- Numeric limits are safe proposed defaults and require workload confirmation.
- Backup/restore and recovery evidence are release requirements but are not
  implemented by this threat-model task.

G1 must approve the threat model, controls, residual risks, required evidence,
and the rule that a real connector cannot weaken the deterministic JSON/Mock
security gates.
