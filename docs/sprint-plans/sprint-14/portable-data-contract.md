# S14-09 — Portable project-data contract

**Status:** `OWNER APPROVED — EVIDENCE REVIEW AND CHECKPOINT PENDING`  
**Contract:** `projecta-portable.v1`  
**Scope:** one logical Projecta project transferred as a user-managed file between supported native Windows installations.  
**The owner approved this contract, not an implemented exporter/importer or cross-machine result.**

## Owner decision

The owner explicitly selected **“Duyệt contract đề xuất”** for the complete
recommendation in §12, including full logical scope, strict compatibility and
resource caps, preserved identities, no merge/overwrite, staged recovery and
plaintext/integrity-only limitations. Evidence review and the delegated
checkpoint remain pending before S14-10/S14-11 implementation.

No permission, membership, session, provider credential, secret, model call, review decision, graph materialization, Google Drive integration, or synchronization is transferred or created by importing an archive.

## 1. Scope and normative terms

This contract is limited to the owner-selected Windows 11 x64, per-user native launcher in the [installation-boundary proposal](installation-boundary-proposal.md). The archive transfers one project that the source installation owner explicitly selects. Google Drive is only a possible manual file transport; Projecta does not connect to Drive or synchronize automatically. This does not cover Compose-volume migration, a raw machine backup, cross-tenant/hosted identity migration, runtime binaries, application upgrades, or signing/release distribution.

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative for the approved future implementation. This contract does not claim those requirements are implemented today.

The exact-capture in-memory browser draft is not durable project storage: users must submit/save work they want to transfer before export. Durable structured Note drafts, persisted candidate edits, candidates awaiting human review, and completed history are different and are included below. An in-flight connector/model operation must reach a terminal state before export; transfer itself never resumes it.

## 2. Authoritative-state inventory

The current local install keeps related logical state in four durable boundaries, not one database. The [memory-layer map](../../initialization/04-Memory-Layer.md) distinguishes domain truth, candidate state, evidence, operational state, and derived projections; the S14-07 installation proposal records the actual native directories. A project export MUST select by the server-owned canonical `projectId`, not a browser-supplied path, handle, graph name, or SQL predicate.

| Boundary and authority | Current state and source reference | `projecta-portable.v1` treatment | If omitted |
| --- | --- | --- | --- |
| Fuseki/TDB2 — authoritative semantic records | `GraphRole` defines five separate project graphs routed by `GraphIriRouter`: `/sources/`, `/candidates/`, `/asserted/`, `/inferred/`, and `/provenance/`. Quick Notes, source versions, exact-span evidence, candidates, lifecycle, asserted records and their provenance live here. See [`GraphRole.java`](../../../services/semantic-core/src/main/java/org/projecta/semanticcore/GraphRole.java), [`GraphIriRouter.java`](../../../services/semantic-core/src/main/java/org/projecta/semanticcore/GraphIriRouter.java), [`QuickNoteCaptureService.java`](../../../services/semantic-core/src/main/java/org/projecta/semanticcore/QuickNoteCaptureService.java), and the [evidence-first authoring contract](../sprint-13/evidence-first-assisted-authoring.v1.md). | Include the complete five-graph logical dataset for exactly one project, serialized as TriG while preserving graph names, stable IRIs, source version/revision/digest, TextAnchor coordinates, candidate lifecycle, assertion/revision/provenance identities and existing inference snapshot. Never export or restore a raw TDB2 directory. | A source-only archive would lose candidates, receipts/provenance, assertions or graph lifecycle; it would not satisfy the Notes, Review Queue and Graph journeys. |
| Local evidence files — authoritative raw source bytes | The active adapter is [`LocalEvidenceStore`](../../../apps/api/src/projecta_api/evidence/local.py), rooted at `PROJECTA_EVIDENCE_ROOT` (`data/evidence` natively). It stores immutable project-scoped content objects and metadata/reference indexes; bytes are SHA-256 checked, content types are JSON or text, and an object is capped at 1 MiB. The port intentionally has no public `list_all`. | Include every complete project-scoped object and its safe typed metadata/reference binding, including objects not yet linked to a committed source when their metadata exists. Read bytes through an owner-only internal project enumeration, verify their exact digest/length, and store them under content-addressed archive paths. If an expected object/metadata pair is incomplete, fail the export rather than silently omit it. Do not copy storage paths or keys. | Connector source content, attached payloads or pending evidence can disappear; an imported source may retain an RDF digest but no usable raw object. Unreferenced incomplete temporary writes are not valid evidence and MUST NOT be promoted. |
| PostgreSQL connector and review state — authoritative operational history | Alembic migrations `0001_connector_operational` through `0011_review_receipts_append_only` define connector installation, setup handles, inbox, run/attempt, cursor, dead-letter and audit records, plus `review_decision_receipts` and `correction_burden_events`. See [`operational/schema.py`](../../../apps/api/src/projecta_api/operational/schema.py), [`connector-operational-storage.md`](../../architecture/connector-operational-storage.md), migrations [`0001`](../../../apps/api/alembic/versions/0001_connector_operational.py), [`0009`](../../../apps/api/alembic/versions/0009_review_decision_receipts.py), [`0010`](../../../apps/api/alembic/versions/0010_correction_burden_events.py), and [`0011`](../../../apps/api/alembic/versions/0011_review_receipts_append_only.py). | Include allowlisted project rows for installations, inbox, terminal runs/attempts, safe cursors, dead letters, connector audit, review receipts and correction-burden events. Keep stable IDs and relationships. Exclude one-time setup handles, raw secret references and unrecognized provider configuration. Imported connector installations are disabled and require destination re-binding/authorization before any user-initiated operation. | Without inbox/run/cursor/history, a transferred connector-backed project can lose replay protection and its incremental position; excluding raw evidence loses replayable payloads. Without receipts, a decision appears to have no audit history. |
| SQLite operational database — durable app workflow state | [`OperationalDatabase`](../../../apps/api/src/projecta_api/configuration/storage.py) creates schema versions 1–3. Separate repositories persist project selections, structured Note drafts, candidate-edit audit and local-suggestion proposal/attempt/budget/authoring-cost records. See [`structured_note_store.py`](../../../apps/api/src/projecta_api/structured_note_store.py), [`structured_candidate_store.py`](../../../apps/api/src/projecta_api/structured_candidate_store.py), and [`local_suggestion_store.py`](../../../apps/api/src/projecta_api/extraction/local_suggestion_store.py). | Include project-scoped structured drafts (including revision/idempotency/committed-note binding), candidate edit history, terminal local-suggestion workflow/proposal/attempt history and project authoring-cost events using an explicit JSON record schema. Do not copy `operational.db`. Exclude active/in-flight suggestion attempts; export waits for completion or returns a safe busy error. Exclude project-selection/session state and per-user/per-project daily budget counters. | Omitting persisted drafts or edits loses user work/audit; omitting a cached proposal can make a previously offered suggestion unavailable (the user may explicitly request a new one later). A fresh destination starts its own selection and suggestion budgets. |
| API read projections and initial project catalog — derived/destination-owned | Project catalog/overview/Graph DTOs are bounded server projections over Semantic Core; [`project-workspace-read-model.md`](../../architecture/project-workspace-read-model.md) says names, counts, freshness and handles are server-derived. Native `config/local-runtime.json` currently stores one workspace; `ProjectaLocal` passes that one ID as `PROJECTA_API_EXPERIENCE_PROJECT_CATALOG`. See [`projecta_local.py`](../../../scripts/projecta_local.py) and [`project_workspace.py`](../../../apps/api/src/projecta_api/project_workspace.py). | Do not package computed opaque UI handles or cached projections. On successful import, create/update the destination's authorized project catalog entry only at commit; regenerate labels/counts/freshness by the existing read path. S14-11 must evolve the current single-workspace configuration/allowlist so a distinct imported project can be added without removing a populated local project. | The imported project will not be selectable even if its records exist. Import must not silently expose unlisted project data or fall back to a previous project. |

### 2.1 Included and excluded boundaries

In addition to the rows above, a package contains source RDF needed to resolve Notes and exact spans, the imported project name/identity, and durable pending-for-human-review state. It preserves candidate vs. asserted vs. inferred graph separation. Existing inferred facts and their provenance/snapshot are copied exactly as source records; transfer does not run a rebuild. Projection/read-model results are recomputed from their authorities, not treated as source data.

The following are deliberately not portable:

- `secret_records.ciphertext`, encrypted credential blobs, provider tokens, secret-store master keys, PostgreSQL passwords, trusted-context secrets, DPAPI `launcher.dpapi`, signing keys or signatures/private keys;
- provider credentials, connector `secret_reference` values, OAuth/AppRole material, browser/OIDC cookies/tokens, login attempts, sessions, membership/authorization grants, local actor configuration, CSRF state, one-time Teams/GitHub setup handles, or destination role assignments;
- `llm_profiles`, configuration audit, environment/host configuration, `.env`, install/launcher configuration other than the explicitly represented project identity/name, local service ports, filesystem/object-store paths, logs, runtime/backup/recovery files, application binaries, Docker/Compose volumes, caches, database clusters or TDB2 internals;
- unsubmitted browser-memory capture state, daily suggestion budget counters, and non-project project-selection/session state;
- opaque connector cursors without a recognized, versioned, secret-free adapter codec. A cursor the exporter cannot safely classify causes an explicit unsupported-state result; it is not copied as an arbitrary string.

The current native experience is single-local-OS-user and uses server-configured actor/project context, not production OIDC. `projecta_oidc_login_attempts`, `projecta_sessions`, and `projecta_project_memberships` exist in the PostgreSQL identity migration for production-shaped deployments but are not native project ownership data. They MUST NOT be transplanted as project permissions. The project ID and historical actor values in semantic provenance remain historical data only.

Connector cursor continuity is retained only for the current explicit codecs: Teams' `teams.v1|timestamp|digest` form and GitHub's canonical `GitHubCursor` v1 base64url watermarks, each validated with its own adapter. The generic cursor port calls its value opaque, so any future/unknown connector cursor MUST be excluded and the affected installation marked for a deliberate full re-sync after reauthorization. The current three connector types are `json-mock`, `teams`, and `github-public-issues`; their connector contract is `connector-contract.v1`. No cursor or imported installation automatically runs.

## 3. Version and compatibility contract

The first implementation MUST advertise and accept only the exact format/contract combinations implemented and tested by that build. The source inventory observed for this proposal is:

| Versioned surface | Observed source value | Compatibility rule proposed for v1 |
| --- | --- | --- |
| Projecta native launcher and API/UI | `APP_VERSION = 0.7.0`; API `apps/api/pyproject.toml` and web `package.json` are `0.7.0`. | Record each producer component version. Initial v1 support is the reviewed native 0.7.0 implementation tuple, not an unbounded `0.x` wildcard. |
| Native runtimes | Python `3.12.10`, Java `21.0.12.1+1`, Fuseki/Jena `6.2.0`, PostgreSQL `16.15`, from `scripts/projecta_local.py`; Semantic Core uses Javalin `7.2.2` and Jena `6.2.0` in `services/semantic-core/pom.xml`. | Include exact runtime compatibility identifiers; do not require identical OS binaries on both endpoints, but require the target's declared portable-contract support. |
| PostgreSQL logical schema | Current Alembic head `0011_review_receipts_append_only`. | Only explicitly supported migration heads; do not import raw database pages or auto-downgrade. The logical record contract pins each exported table set/schema version. |
| Application SQLite schema | `schema_migrations` versions 1, 2, and 3 in `configuration/storage.py`; other application repositories create named tables. | Export logical records with explicit table-record schema versions; do not ship the SQLite database file. |
| Connector, evidence, review-receipt and correction contracts | `connector-contract.v1`, `connector-evidence.v1`, `review-receipt.v1`, and `correction-burden.v1`; connector source object limits are 1 MiB/object, 100 events/run, 10 MiB/run. | Manifest declares every contract version used. Unknown contract versions fail before destination mutation. |
| Ontology and shapes | `bootstrap_fuseki.py` loads the core/communication (0.1.0), provenance/temporal (0.2.0), evidence (0.3.0), extraction (0.4.0), and M4 modules. `ontology/m4-retrieval.ttl` declares `v/0.5.0`; the separate [`v0.5.1 compatibility baseline`](../../architecture/v0.5.1-compatibility-baseline.md) records the released product baseline and says no Sprint 11 ontology bump is implied. | Record the exact module/versionIRI inventory plus SHA-256 of the ontology, SHACL shapes and inference-rule assets that govern the archive. The importer compares against an explicit supported fingerprint. No new terms and no silent vocabulary or data migration. |
| Native recovery manifest | `DATA_CONTRACT_VERSION = 1` in `projecta_local.py` is used by local backup/runtime metadata. | It is **not** the portable archive version. Use the separate exact `"portableContract": "projecta-portable.v1"` field. |

The ontology module inventory above is intentionally not collapsed into a fabricated single `0.5.1` RDF version: product compatibility documentation and individual `owl:versionIRI` values represent different things. A future implementation must emit and compare exact ontology/shapes/rules asset fingerprints; if it cannot establish that mapping from the packaged assets, it fails closed and records the blocker rather than guessing.

A future importer may add a named migration only under an explicit compatibility matrix and verification. Without one, an older/newer application, schema head, connector/evidence/receipt contract, ontology module, shape or rule fingerprint is `UNSUPPORTED_VERSION`; it MUST NOT partially import, rewrite graph identities, auto-migrate data, or lower a schema.

## 4. Archive format and bounded payload

### 4.1 Container and names

Use a single `.projecta` ZIP file with UTF-8 names and only stored/Deflate members. ZIP encryption is forbidden. The archive contains one `manifest.json` and only the fixed path families below. ZIP CRC is checked in addition to each manifest digest. Reject duplicate names (including case-fold collisions), absolute or drive-qualified paths, `.`/`..`, backslashes, symlinks/reparse entries, special files, unlisted/missing files, unknown paths, unsupported compression/encryption, malformed UTF-8/JSON, duplicate JSON keys, and a project graph outside the declared scope. Never extract an untrusted path directly into a live data root.

| Archive member | Logical contents |
| --- | --- |
| `manifest.json` | Strict v1 envelope, project/producer/schema/ontology identities, counts and exact inventory of every payload member. Unknown fields are rejected. |
| `payload/semantic/project.trig` | Five named project graphs with their original graph IRIs and complete RDF records. No global ontology graph or other project's graph. |
| `payload/evidence/sha256/<digest>.bin` | Exact immutable evidence bytes keyed by their lowercase SHA-256. The manifest maps the content digest to each original evidence reference and safe metadata. |
| `payload/application/project-workflows.json` | Canonical JSON array/object encoding the allowlisted drafts, candidate edits, terminal suggestion state and project-scoped authoring-cost records. |
| `payload/operations/connectors.json` | Canonical allowlisted project connector rows and recognized versioned cursor values; no secret or setup/session data. |
| `payload/receipts/review-decision-receipts.jsonl` | Exact append-only receipt records, ordered by project/item/sequence. |
| `payload/receipts/correction-burden-events.jsonl` | Exact append-only correction event records, with stable receipt/materialization/inference digest references. |

The archive contains logical records, not `postgres/`, `fuseki/`, `operational.db`, SQLite pages, `.env`, file-store roots, service config, binaries or backup bundles. Evidence payload paths are archive-local content digests, never absolute or user-controlled storage keys.

### 4.2 Required manifest envelope

The manifest is strict UTF-8 JSON. The exact top-level members are `portableContract`, `exportId`, `exportedAt`, `project`, `producer`, `evidenceReferences`, `counts`, and `entries`; every nested object is also closed to unknown fields. For a given producer build, the exporter uses UTF-8 without BOM, no duplicate keys, deterministic property/member ordering, UTC RFC 3339 timestamps, integer byte counts, and lowercase 64-hex SHA-256 digests. `exportId` is a new UUIDv4 per export, not a project identity or permission. The following is a **JSON shape fixture only**; it is not a valid complete archive inventory:

```json
{
  "portableContract": "projecta-portable.v1",
  "exportId": "6ac2e8e4-4e80-4bd8-9d28-75ad0cfab014",
  "exportedAt": "2026-10-02T12:00:00Z",
  "project": {
    "projectId": "checkout-modernization",
    "projectName": "Checkout modernization",
    "tenantId": null
  },
  "producer": {
    "projectaVersion": "0.7.0",
    "apiVersion": "0.7.0",
    "webVersion": "0.7.0",
    "nativeRuntime": {
      "python": "3.12.10",
      "java": "21.0.12.1+1",
      "fuseki": "6.2.0",
      "postgresql": "16.15",
      "semanticCore": {
        "javalin": "7.2.2",
        "jena": "6.2.0"
      }
    },
    "postgresAlembicHead": "0011_review_receipts_append_only",
    "sqliteSchemaVersions": [1, 2, 3],
    "connectorContract": "connector-contract.v1",
    "reviewReceiptContract": "review-receipt.v1",
    "correctionBurdenContract": "correction-burden.v1",
    "ontologyAssets": [
      {
        "assetType": "ontology",
        "path": "ontology/m4-retrieval.ttl",
        "versionIri": "https://w3id.org/projecta/ontology/v/0.5.0",
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
      }
    ]
  },
  "evidenceReferences": [],
  "counts": {
    "namedGraphs": 5,
    "evidenceObjects": 0,
    "workflowRecords": 0,
    "connectorRecords": 0,
    "reviewReceipts": 0,
    "correctionBurdenEvents": 0
  },
  "entries": [
    {
      "path": "payload/semantic/project.trig",
      "role": "semantic-project",
      "mediaType": "application/trig",
      "sizeBytes": 1,
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    }
  ]
}
```

Normative shape and cross-field validation:

- `project` has exactly `projectId`, `projectName`, and `tenantId`. `projectId` matches `[a-z0-9][a-z0-9-]{0,62}`; `projectName` is non-empty, trimmed, control-character-free, and at most 128 characters (a larger source name is an explicit `UNSUPPORTED_STATE`, never truncated). Only `tenantId: null` is supported by the native profile.
- `producer` has exactly the version fields shown above. `ontologyAssets` is the exact deterministic inventory of every packaged ontology module, SHACL shape and inference-rule asset; each entry has `assetType` (`ontology`, `shape`, or `inference-rule`), package-relative `path`, nullable declared `versionIri`, and the asset's SHA-256. A version IRI is never invented for an asset that has none.
- `evidenceReferences` is sorted by `evidenceReference`; each closed object contains exactly `evidenceReference`, `sha256`, `sizeBytes`, `contentType`, `createdAt`, `retentionClass`, `retainUntil`, `sourceReference`, and `contractVersion`. The manifest `projectId` is the evidence metadata's `project_scope`; a conflicting scope is rejected. Content types are only `application/json` or `text/plain`, an object is at most 1 MiB, and the v1 native retention class is `connector-default`; unknown classes fail rather than disappear. `contractVersion` is `connector-evidence.v1`. Nullable `retainUntil` and all original reference/timestamp/digest values are preserved. A source reference is historical metadata only and is never fetched during import.
- `counts` has exactly the six non-negative integer fields shown. `namedGraphs` is exactly 5; `evidenceObjects` equals the evidence-reference and evidence-member counts; `workflowRecords`, `connectorRecords`, `reviewReceipts`, and `correctionBurdenEvents` equal the decoded allowlisted records in their respective members.
- Every `entries` item has exactly `path`, `role`, `mediaType`, `sizeBytes`, and `sha256`. Paths are unique, case-fold unique, normalized archive-relative names. The entries inventory contains exactly the five mandatory fixed payload members in §4.1 plus one member per evidence object; it excludes `manifest.json`, which cannot self-hash. Each listed size/digest must match the exact member bytes, and no extra archive entry is allowed.
- Entry `role` is exactly one of `semantic-project`, `application-workflows`, `connector-state`, `review-receipts`, `correction-burden-events`, or `evidence-object`; `mediaType` is fixed for each structured payload and equals the validated allowlisted content type for an evidence object. Evidence paths are `payload/evidence/sha256/<lowercase-sha256>.bin`, with the filename digest equal to the metadata/member digest.
- The role/media mapping is fixed: `semantic-project` → `application/trig`; `application-workflows` and `connector-state` → `application/json`; `review-receipts` and `correction-burden-events` → `application/x-ndjson`; `evidence-object` → its manifest-validated `application/json` or `text/plain`. No other role or media type is supported.
- The versioned JSON payload roots each carry `schemaVersion: 1` and closed allowlists: `project-workflows.json` has `structuredNoteDrafts`, `candidateEdits`, `suggestionWorkflows`, `suggestionAttempts`, and `authoringCostEvents`; `connectors.json` has `installations`, `inbox`, `runs`, `attempts`, `cursors`, `deadLetters`, and `auditEvents`. Rows use the exact allowlisted project-scoped logical fields of the cited stores/migrations, in camelCase, not raw SQL pages; project IDs and stable foreign references must agree with the manifest. Setup handles, credential fields, and recognized-unsafe cursors are absent. Imported connector installations are disabled regardless of their source state.
- Every explicit `projectId` equals the manifest identity. Where a source row stores only a project digest, the serializer verifies its original source rule before inclusion; in particular, SQLite `authoring_cost_events.project_digest` must equal the existing `sha256:<lowercase-hex>` digest of the manifest `projectId`. It is never treated as an unscoped record.
- `review-decision-receipts.jsonl` contains exactly the logical columns of `review_decision_receipts` (camelCase `receiptId`, `projectId`, `actorDigest`, `authorizationDigest`, `itemKind`, `itemHandleDigest`, `decision`, `candidateRevision`, `sourceVersionDigest`, `sourceVersionRevision`, `constrainedContractVersion`, nullable `evidenceDigest` and `previousDecisionDigest`, `idempotencyDigest`, `requestDigest`, `sequence`, `occurredAt`, and `receiptDigest`). The producer declares `review-receipt.v1`; the record does not invent the API's transient `outcome` field. Rows remain ordered by project/item/sequence and are chain-verified.
- `correction-burden-events.jsonl` has exactly `eventId`, `projectId`, `itemKind`, `itemDigest`, `assertionDigest`, `sourceVersionDigest`, `sourceVersionRevision`, `reviewReceiptDigest`, nullable `materializationRevision` and `inferenceRevision`, `correctionCategory`, `correctionDimensions`, `reviewOutcome`, `semanticEditCount`, `reviewLatencyMs`, `materializationState`, `inferenceState`, `idempotencyDigest`, `requestDigest`, `occurredAt`, and `eventDigest`, mapped from migration `0010`. The producer declares `correction-burden.v1`; the record does not invent the API's transient `outcome` field. Neither receipt nor correction records may be regenerated, normalized into new decisions, or edited during transfer.

The sample's one-byte member and zero digests are deliberately synthetic. It demonstrates JSON syntax and typed envelope fields only; it does not have the mandatory full member list, hashes of payloads, complete ontology inventory, or valid payload bytes and MUST NOT be treated as a package fixture. The archive tables and cross-field rules above, rather than this abbreviated specimen, define a valid package.

The manifest's producer inventory records the exact supported application/runtime/schema/connector/ontology tuple. A destination compares it against an explicit implementation compatibility matrix and exact asset fingerprints before staging. Any unavailable fingerprint or unknown field/version is `UNSUPPORTED_VERSION`; there is no inferred compatibility or silent migration.

### 4.3 Hard resource bounds proposed for owner approval

| Limit | v1 proposal | Rationale and failure behavior |
| --- | ---: | --- |
| Complete archive file | 2 GiB | Bounds manual transport, archive reads and staging. Larger workspaces fail with a clear export-size result; no truncation/splitting. |
| Total expanded payload | 4 GiB | Sum of uncompressed bytes for every archive member, including `manifest.json`; bounds archive bombs and staging exhaustion independently of compression ratio. Check before/during decompression. |
| Manifest | 2 MiB | Enough for bounded entries/metadata while preventing unbounded manifest allocation. |
| Total ZIP entries | 4,096 | Covers up to 2,048 evidence objects plus fixed records with finite parser overhead. |
| Evidence objects | 2,048, each at most the existing 1 MiB object cap | Reuses the actual adapter per-object ceiling; total-expanded cap may impose a lower effective count. |
| Semantic TriG | 512 MiB and 1,000,000 triples total | Combined bound across the one project TriG member/five graphs; bounds parsing/SHACL work and rejects the whole export/import above either limit. |
| Logical records across workflows, connectors, receipts and correction events | 250,000 | Sum of all records in both JSON/JSONL operational members; bounds typed-row validation and staging, rejecting input over the cap as a whole. |

These are proposed policy values, not measured product maxima or proven memory guarantees. No owner workspace was inspected and no production-size distribution is known. Before S14-10/11 implementation, the owner must approve these bounds; S14-11 must test each boundary on disposable synthetic data and report the supported resource envelope. Changing a bound after contract approval requires an explicit contract-version decision if it changes compatibility.

## 5. Identity, provenance, and semantic continuity

1. Preserve canonical `projectId`, all project graph IRIs and every existing stable project/source/source-version/candidate/assertion/activity/receipt/evidence ID, digest, revision, source offset/span and timestamp exactly. V1 does not re-key IRIs or hashes to fit a destination project, and does not merge two projects.
2. Preserve the distinction between source, candidate, asserted, inferred and provenance graph roles. Candidate review and assertion/materialization are independent transitions. Import writes the archived state as state; it MUST NOT call capture, validation-to-approved, receipt-recording, confirmation, assertion-materialization, inference-rebuild, extraction, model/provider, connector, retry, webhook, or other external-action operations.
3. Copy the complete inferred graph and its existing `InferenceSnapshot`/revision as a derived snapshot, not new authority. Preserve whether it was current/stale at the source snapshot. Do not recompute or silently label stale inference current. Existing explicit authorized rebuild remains a separate action. API workspace and Graph projections are recomputed after import.
4. Review receipts are history, not permission. Preserve the exact `receipt_id`, sequence, decision, source/candidate revisions, `previous_decision_digest`, actor/authorization/item/idempotency/request/receipt digests, timestamp, and evidence/contract references. Verify record digests and each sequence/previous-digest chain against the source rows. Preserve correction-burden events and their referenced receipt/materialization/inference revisions. Do not issue a new “import approval” receipt or rewrite a copied receipt.
5. Preserve source actor literals in RDF and actor digests in receipts/audit as historical attribution. They do not identify or authorize a destination user. Current native experience uses the fixed configured actor `local-operator`; the model has no device-bound individual identity that proves who actually used another machine. Do not equate matching actor strings across installations, merge identities, infer current-user permissions, copy memberships/sessions, or claim stronger authorship authenticity than the source records provide.
6. A destination's own actor, project catalog and authorization policy remain authoritative. A local user with permission to import into a destination explicitly adopts the incoming project identity. Imported connector state is disabled until a destination owner reconfigures and reauthorizes that connector; a cursor is only a provider checkpoint, not authentication. Destination provider credentials are entered/re-bound separately through Settings. Historical source identity/configuration is never a substitute for consent or credentials.
7. RM-63 production materialization remains disabled by default and requires its existing semantic-owner authorization. Archive parsing or import does not grant that authorization. No ontology term, shape, inference rule or materialization lock is changed by this contract.

8. Durable application workflows may contain installation-local handles and idempotency keys. They are not project identity or authorization. Export resolves draft/edit references to stable project/candidate/note IDs, preserves the committed payload, revisions, edit history, timestamps, historical actor attribution, terminal suggestion records and append-only cost events, but never makes a source handle or key callable on the destination. The destination mints new local draft/edit handles and idempotency keys; inability to resolve a complete stable reference fails export/import rather than attaching history to another item.

## 6. Destination ownership, compatibility, and conflict policy

### 6.1 Authorization and project ownership

The archive is untrusted input and cannot assert its own destination rights. Before staging, the current destination actor must be authorized by the destination installation to add/adopt the project and confirm the displayed project name, source ID, byte count, source/export time, and excluded-secret notice. The destination retains control of its data and local project catalog. Native v1 applies only to its one-local-OS-user trust boundary; production OIDC membership, multi-tenant hosting and tenant reassignment are unsupported.

All source-project records, graph IRIs, evidence scope and relational project predicates must agree on the one manifest `projectId`. Reject unknown project IDs, cross-project edges, receipt/evidence references outside that scope, unknown RDF named graphs, unrecognized columns/fields, and a manifest with a non-null unsupported tenant. Filtered API handles are generated at the destination and never copied as permission.

### 6.2 Existing-project collisions; no hidden merge

- If the imported `projectId` is not present, add it as a new project while keeping every existing destination project and state intact.
- If it is the native first-run ID `my-projecta-workspace`, it MAY be adopted only when a read-only, complete destination check proves the untouched bootstrap placeholder. That means the asserted graph contains exactly the two native seed triples for the configured project IRI—`rdf:type projecta:Project` and `projecta:name` equal to the untouched local workspace display name—and there are no other triples in any project graph; no project workflow/draft/edit/suggestion rows or project authoring-cost/budget-counter rows; no evidence metadata/objects; no connector, receipt or correction rows; and no user-written workspace configuration changes. Import replaces only that exact seed pair in its isolated stage with the archive's five graphs. On successful same-ID adoption, the owner-confirmed archive name becomes the workspace's destination display name in the same catalog/config commit; the actor remains destination-local. The UI says the seed-only placeholder and its displayed name are being adopted. Any additional or changed state makes this a normal collision and blocks import.
- If an existing non-empty project has the same ID, reject with a conflict. Do not merge, overwrite, remap IDs, replace the project's name silently, or offer an “import anyway” path. A future merge is a separate semantic design and contract.
- Reimport of an already committed exact archive is an idempotent “already imported” result only when the destination ledger matches both `exportId` and the exact archive SHA-256. A different archive for the same project ID is a conflict, not a delta/merge. The ledger is destination-owned operational metadata outside the archive.
- Preserve global relational IDs when possible. If an installation/event/run/attempt/receipt identity collides with a different destination project or row, reject before apply; do not coalesce unrelated records. Internal auto-generated audit surrogate keys may be allocated on import only where every relationship is rewritten within that same logical record set and they are not public/stable IDs; otherwise reject the conflict.

### 6.3 Fresh native installation behavior

A fresh native install is not empty: `provision_first_run_workspace()` creates `config/local-runtime.json` with display name `My Projecta Workspace`, deterministic project ID `my-projecta-workspace`, and actor `local-operator`. The launcher passes that workspace ID and name as `PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS`; `bootstrap_fuseki.py` writes exactly two project seed triples into its asserted graph (`rdf:type projecta:Project` and `projecta:name`). The launcher currently supplies only that workspace ID in `PROJECTA_API_EXPERIENCE_PROJECT_CATALOG`. Therefore:

- A different incoming project ID is added beside the first-run workspace. S14-11 must extend the persisted destination project registry/configuration and server allowlist to represent both; it must not overwrite the single local workspace setting or make the imported project invisible.
- An archive from another default-named first-run installation may have the same `my-projecta-workspace` identity. It can populate this destination only through the exact seed-only placeholder adoption check above. The staged apply removes only those exact two untouched seed triples, installs the archived state, and atomically changes the placeholder display name to the owner-confirmed archive name; it never deletes or renames user-authored project content. If the default workspace already has any user state, import is rejected; the importer does not rename/remap or erase it.

This is a necessary downstream implementation seam, not a currently available multi-project import feature.

## 7. Consistency, staging, apply, and recovery

### 7.1 Export point

PostgreSQL, SQLite, Fuseki/TDB2 and evidence are separate state authorities; no current cross-store transaction gives a snapshot by itself. S14-10 MUST create one no-writer epoch before enumerating any of them:

1. Require explicit project selection and owner confirmation; acquire the one native launcher instance lock. Pause new project writes, connector dispatch, evidence retention/purge, local suggestions and any other project mutation through a server-owned maintenance/write fence. Drain existing operations to terminal outcomes. If any connector run/attempt or suggestion attempt is active, return a safe `EXPORT_BUSY` result; do not silently cancel or resume it.
2. Keep the write fence held for the entire collection and digest pass. Read PostgreSQL and SQLite under consistent read-only transactions and enumerate only selected-project records. Read the five named graphs under a Semantic Core/TDB2 read transaction/typed export boundary. Enumerate immutable evidence metadata/objects for the same project, verify referenced bytes and SHA-256, and include complete stable objects only. Unknown or incomplete records fail the whole export.
3. Capture the source catalog/project revision, supported migration heads, graph role inventory, object refs and per-payload digest in the manifest. Recheck the frozen revision vector before finalizing. Any write attempt, revision mismatch, unavailable store, missing evidence or capacity overflow aborts and leaves the source unchanged.
4. Write to a same-volume restricted temporary `.partial` archive, fsync/close, reopen and validate every member, ZIP CRC and SHA-256, then atomically rename to the final `.projecta` path. An interruption leaves no apparently complete final file. The source data remains unchanged.

The native launcher already owns process lifecycle/locking; Fuseki is configured for one local TDB2 owner; evidence writes are immutable/content-addressed; local data is grouped under one per-user root. These are feasible seams. There is no current project export API, global write fence, or multi-store portable snapshot protocol. S14-10 must implement and prove them; do not confuse the local `BackupManager`'s stopped-service whole-state snapshot with this logical export.

### 7.2 Import validation and application

S14-11 MUST validate the complete archive before touching live project state:

1. Enforce archive byte/count/expanded-size bounds while streaming; reject path/entry/ZIP/JSON violations and any missing/extra member.
2. Check every file digest/length, project ID/tenant agreement, supported producer/schema/ontology fingerprint, allowlisted record fields, referential integrity and all version-specific cursor/evidence/receipt contracts.
3. Parse TriG with the supported semantic stack; require exactly the five canonical graphs for the declared project, project isolation across subject/object/project predicates and source linkage, supported SHACL conformance, valid inference snapshot semantics, valid evidence references and digest/length/content-type matches. Verify relational foreign references, append-only receipt sequences/digests/chains, correction-event receipt references and the schema's project predicates. Reject arbitrary query/IRI/path input; never interpret archive content as a command.
4. Recheck destination authorization, catalog/project collision policy, exact pristine-placeholder eligibility and available staging/rollback space. Generate a preview; ask the owner to confirm before apply. Unsupported versions, nonconformance, collision, cancellation or disk shortage leave live data and catalog unchanged.
5. Stage a logical import in a private, same-volume recovery area against a clone/staging copy of affected destination data. Validate the staged result using the destination application/Semantic Core contract without exposing it in the selectable project catalog. Use normal migrations for the destination; do not import or replace source database pages.
6. Record a durable destination-owned import journal with archive digest/export ID, destination project ID, old catalog revision, stage paths under app control, snapshot identity and a finite phase. With all Projecta services quiesced under the launcher lock, apply only project-scoped additions to the staged data and publish the destination project registry last. Existing projects and unrelated data are not merge targets.
7. Before project catalog publication, any error rolls back the stage and restores the pre-import local recovery snapshot; after interruption, startup MUST detect the unfinished journal before starting API/Semantic Core and either finish the recorded commit or restore the previous state. Never serve a mixed/partially imported state. On success, write the committed import-ledger record, atomically expose the project, restart and read back the project catalog and one bounded project/evidence/receipt projection; remove temporary state only after verified commit while retaining the ordinary local recovery point according to native policy.

The existing `BackupManager` demonstrates a local pattern—requires a quiescent runtime, verifies a manifest, stages copies, moves old/new state with rollback and keeps failed state—but it snapshots `data`, `config/local-runtime.json`, `config/installation.json` and `secrets/launcher.dpapi` as one local recovery set. It is not portable, does not filter by project, and does not establish restart recovery for a portable importer. The importer must not export those roots or copy source secrets to the destination. S14-11's restart/fault tests MUST exercise process interruption after each apply phase, including registry publication, and prove on restart either (a) exact pre-import state with the archive still uncommitted or (b) exact complete imported state with the project selectable—never a mixed state.

Because the current PostgreSQL receipts and correction events are append-only, import must not invoke the receipt API to manufacture new history or attempt ordinary UPDATE/DELETE rollback of already committed receipts. The apply implementation must keep staged receipt rows uncommitted/unpublished until the recovery protocol can prove a complete commit, and test the database triggers and crash boundaries. If a safe staged commit cannot be demonstrated, fail closed without inserting them.

## 8. Integrity, authenticity, confidentiality, and secrets

The proposed v1 archive is **not encrypted and not signed**. SHA-256 entry digests, ZIP CRC and internal references detect accidental corruption or a payload changed without a matching manifest; they do not hide content, prove who exported it, or authenticate a manifest that an attacker can rewrite together with every digest. A structurally valid, consistently re-hashed malicious archive cannot be distinguished from a genuine one in unsigned v1. Semantic/schema checks reduce malformed-input risk but do not establish business truth or sender identity.

No existing key is suitable or authorized to sign this archive: the DPAPI `CurrentUser` material is machine/account-bound; the application secret-store key and provider credentials are forbidden; update/package signing keys are owner-held and cannot be repurposed or placed in an archive. If the owner requires authenticity or confidentiality beyond a user confirmation and integrity checks, v1 must not be approved until a separate owner-controlled signature/encryption/trust-anchor scheme is designed and authorized. This proposal does not create or retrieve keys.

The archive intentionally contains raw project text and possibly connector message/document content as well as source IDs, human decisions, actor digests, external references/cursors and historical audit. Treat it as sensitive data. Export must show a clear warning and require confirmation that the user is allowed to move the selected project and its source payloads. Manual Google Drive/other transport can expose the file to the account/provider and anyone with link/share access; use private access, do not create public links, remove unnecessary sharing, and do not transfer restricted data without the owner's data-handling authorization. Destination import must show the same warning. No claim that the archive is safe to store in a third-party drive is made.

Strict export allowlists MUST make these exclusions structural—not a best-effort text search. In particular, never read/copy `launcher.dpapi`, local `secrets/`, `.env`, host config, OIDC/browser sessions, database credentials, encrypted credential blobs, secret references, OAuth tokens, OpenBao/AppRole material, or signing keys into any archive member. A connector installation imported without its credential is disabled until its destination owner rebinds a valid secret and explicitly authorizes it. Provider settings must be re-entered; lost/omitted credentials are not restored from source metadata.

## 9. Consumer acceptance vectors for S14-10/11 and S14-12

These are required future consumer-visible vectors, not checks performed by this proposal:

| Vector | Required result |
| --- | --- |
| Export/import a populated project through an ordinary manual file transfer | The destination can select the imported project and use Notes, exact source detail/offsets, Review Queue, Graph and project overview. All five graph roles, source-version IDs/revisions/digests, exact anchors, evidence bytes/references, candidate states, receipts and allowed operation history match the source snapshot. No raw ID entry is required from the UI. |
| Receipt continuity | For each candidate/item, ordered review history returns the exact same receipt IDs/digests, decisions, sequence, previous-digest chain, source/candidate revision binding and historical actor/authorization digests. No additional receipt/approval is created by import. |
| Candidate/asserted/inferred separation | Candidate remains candidate; asserted state is copied only if already present; inferred facts and stale/current snapshot are unchanged. No model/provider call, extraction, validation-to-approval, confirmation, RM-63 materialization, inference rebuild, outbound action or connector sync occurs. |
| File corruption or partial input | Changed payload with original manifest, changed manifest with mismatched entries, truncated file, CRC/digest/size mismatch, missing or extra entry, malformed JSON/TriG/JSONL, broken receipt chain, missing evidence or invalid graph/project link is rejected before live apply. A maliciously re-hashed valid archive is not an authenticity-detectable condition in unsigned v1 and must be disclosed to the user. |
| Unsupported version/schema/ontology/cursor/limit | Reject before staging/apply with an actionable finite error and no partial state. No implicit migration, cursor guess or raw DB fallback. |
| Authorization/cross-project/cross-tenant | Unauthorized actor, unsupported tenant, mismatched `projectId`, graph/reference/row from another project, or altered source scope is rejected without disclosing unrelated project existence. |
| Fresh native target | Keep the first-run workspace and add a distinct imported ID to the destination catalog; if the archive has the same ID, allow adoption only for the exact untouched seed-only placeholder (two known asserted seed triples and no other project state). Show the decision. All other collisions fail without merge or overwrite. |
| Existing destination, pending data and exact replay | Non-colliding import does not change any existing project's graphs, drafts, evidence, connectors, receipts, credentials, selections or pending state. Controlled failure/cancel/unauthorized import preserves the full pre-import state. Exact archive replay is a no-op; changed bytes for an already-used project ID conflict. |
| Source mutation/concurrency | Start a competing write during export; exporter maintains its no-writer epoch or aborts on revision drift and never emits a mixed point. Concurrent destination writes/imports cannot alter the target while staged apply is committed; stale catalog/selection results fail explicitly. |
| Restart/rollback fault injection | Interrupt after evidence staging, SQLite preparation, PostgreSQL receipt staging, semantic graph preparation, directory/root move, catalog update and commit marker. On restart prove exact old or exact complete new state, all existing data intact, no mixed selectable project, and no broken append-only receipt chain. |
| Connector continuity and rebind | Verify only recognized Teams/GitHub cursors survive exactly; imported installations are disabled and do not execute. Without target credentials no token/session is present and a connector cannot run. Unsupported cursor reports explicit full-resync-required status, never silently skips or auto-replays. |
| Confidentiality/exclusions | Inspect only a synthetic archive with test values and prove no source credential, ciphertext, secret reference, master key, DPAPI, session, host config or signing key is present. Verify the UI warns the user that source content is plaintext and may be sensitive. |
| User-facing path | A user exports a selected project from A, sees file name/size/digest and data warning, moves one file manually, chooses Import on B, previews/authorizes it, then selects the project. Instructions say the browser file is not a backup, Drive is manual, credentials must be rebound, and errors preserve the destination. |

S14-10 owns the consistent export and archive; S14-11 owns complete validation, explicit owner authorization, non-interfering import, project-catalog inclusion and crash/recovery proof; S14-12 owns the actual separately authorized cross-machine trial. Documentation or a schema fixture does not pass those product/runtime criteria.

## 10. User flow proposal (not current product capability)

1. On installation A, select one authorized project and choose **Export project**. Show included source/evidence and audit scope, exact size limits, plaintext/transport warning, and an owner confirmation before quiescing. On success, provide one `.projecta` file and local SHA-256 for corruption checks; do not label that digest as a signature.
2. Move only that file manually through the owner's approved private channel (Google Drive is not integrated). Do not upload a raw machine backup or credentials.
3. On installation B, choose **Import project** from Projects/launcher handoff. Select the file, wait for full validation, review project identity/version/size/excluded-secret warning and the destination collision/first-run action, then explicitly authorize apply.
4. After success, the imported project appears in the destination project chooser and is not selected implicitly. Rebind connector/model settings separately if desired; no connector/provider runs until the user configures and explicitly invokes it. On any incompatibility, conflict or interruption, show the finite result and preserve destination state.

This user flow must be built against the existing Application API and native launcher; the browser must not call Fuseki or access raw filesystem paths. No automatic Drive upload, connector, sync, background retry, telemetry, or remote publication is added by this contract.

## 11. Evidence and known limits

The repository confirms separate native `data/postgres`, `data/fuseki`, `data/sqlite`, `data/evidence`, local configuration, DPAPI secrets and local backup/recovery boundaries; the installation proposal documents service lifecycle and stop/restore recovery. The connector evidence, connector operational, structured Notes, workspace and review receipt contracts provide the logical field/version sources cited above. `GraphRole`/`GraphIriRouter` and the Semantic Core source confirm the five project graphs and single project routing. The plan and user journeys require preserving source-bound review, project isolation, non-materializing manual outcomes and cross-installation usability.

The following are not established and must remain open until implemented/tested or owner-decided:

- The owner approved `projecta-portable.v1`, but no implemented runtime archive schema, exporter, importer, destination project registry migration, cross-store write fence, signature, or archive encryption is established by this document. No cross-machine runtime result exists. The embedded JSON shape fixture is not a valid package.
- No owner workspace or live source dataset was read; no actual project size/count distribution or production tenant/identity state is inferred. The numerical archive caps are approved policy limits, not measured resource guarantees.
- Native first-run configuration and its API project catalog currently represent one project; adding a distinct imported project requires a reviewed implementation change. A fresh-project same-ID collision can be resolved only by the proposed pristine-placeholder adoption check.
- Existing local `BackupManager` recovery is whole-installation restore and includes protected secrets/config in the local recovery set. It is not evidence for project export/import or cross-store crash recovery.
- v0.5.1 product compatibility documentation and individual ontology module version IRIs must be represented separately as specified in §3. The packaged ontology asset fingerprint support must be verified before implementation can claim compatibility.
- The owner accepted that this design transfers sensitive raw source payloads in plaintext and does not authenticate the sender. User warnings and trusted manual transport remain mandatory; approval does not create confidentiality or authenticity.
- No clean-host, cross-machine, production authentication, signing, publication, Compose-data migration, public release, or `1.0.0` evidence follows from contract approval.

## 12. Material owner choices and recommendation

| Owner choice | Recommended contract | Material alternative and consequence |
| --- | --- | --- |
| Transfer scope | Approve a complete one-project logical snapshot: all five semantic graphs, project evidence, durable project drafts/edit history, append-only receipts/correction history, terminal project connector state and recognized safe cursors; credentials/session/setup state excluded and connectors disabled until destination rebind. | A reduced semantic-only package is simpler but loses usable raw evidence and connector replay/receipt continuity; it does not meet the complete transfer purpose. Full raw machine snapshots are expressly rejected because they move secrets/host state and conflict with the native installation boundary. |
| Fresh destination and collision | Preserve stable source IDs. Add a distinct project beside the seeded default workspace; adopt same-ID first-run only if the exact two-triple seed-only placeholder predicate passes. Reject all other same-ID conflicts; no merge/overwrite/remap. | Remapping or merging IDs changes semantic IRIs, receipt digests and provenance semantics and requires a separate contract. Requiring an empty installation is incompatible with native first-run provisioning. |
| Archive security | Approve explicit integrity-only/plaintext v1 with strong UI warning, per-entry hashes, full validation and owner confirmation; do not claim authenticity/confidentiality. | Require signature and/or encryption before any transfer: viable only after the owner authorizes a key/trust/recipient scheme outside DPAPI, provider secrets and package-update signing; absent that decision, implementation is blocked rather than inventing a key. |
| Resource limits | Approve the explicit §4.3 ceilings as initial hard caps, with boundary/fault tests and no truncation. | Larger/uncapped transfers weaken safe staging and need a different measured resource envelope and explicit revised decision. |

**Approval question:** “Do you approve `projecta-portable.v1` with the full logical project scope, exact compatibility and hard limits in §§2–4, preserved identities/receipts and no materialization in §5, first-run/collision and recovery behavior in §§6–7, and the explicit plaintext/integrity-only limitations in §8, so S14-10 and S14-11 may implement exactly this contract? If not, which listed material choice changes?”

**Current decision:** owner approved the complete recommendation by selecting “Duyệt contract đề xuất”. No ontology change or runtime PASS is implied. The approval is recorded append-only in `.agents/memory/decisions.md`; S14-09 evidence review and delegated checkpoint remain pending.

## Source map

- Owner transfer requirement and task order: [Sprint 14 requirements §5](../sprint-14-requirements.md), [Sprint 14 plan S14-09–12](../sprint-14.md), [selected user journeys](user-journeys.md).
- Native installation, first-run config, secrets and local backup boundary: [installation-boundary proposal §§4–5](installation-boundary-proposal.md); [`ProjectaPaths`, `WorkspaceConfig`, `BackupManager`](../../../scripts/projecta_local.py); [`bootstrap_fuseki.py`](../../../scripts/bootstrap_fuseki.py); [`LocalFusekiServer.java`](../../../services/semantic-core/src/main/java/org/projecta/semanticcore/LocalFusekiServer.java).
- Current authoritative semantic/data paths: [`GraphRole.java`](../../../services/semantic-core/src/main/java/org/projecta/semanticcore/GraphRole.java), [`GraphIriRouter.java`](../../../services/semantic-core/src/main/java/org/projecta/semanticcore/GraphIriRouter.java), [`QuickNoteCaptureService.java`](../../../services/semantic-core/src/main/java/org/projecta/semanticcore/QuickNoteCaptureService.java), [`OperationalDatabase`](../../../apps/api/src/projecta_api/configuration/storage.py), [`LocalEvidenceStore`](../../../apps/api/src/projecta_api/evidence/local.py), [`operational/schema.py`](../../../apps/api/src/projecta_api/operational/schema.py), [`ReviewDecisionReceiptRepository`](../../../apps/api/src/projecta_api/extraction/review_receipts.py).
- Connector contract/cursor formats: [`connector-operational-storage.md`](../../architecture/connector-operational-storage.md), [`connector-evidence-storage.md`](../../architecture/connector-evidence-storage.md), [`connector/contracts.py`](../../../apps/api/src/projecta_api/connectors/contracts.py), [`teams.py`](../../../apps/api/src/projecta_api/connectors/teams.py), [`github_public_issues.py`](../../../apps/api/src/projecta_api/connectors/github_public_issues.py).
- Project catalog and derived UI: [`project-workspace-read-model.md`](../../architecture/project-workspace-read-model.md), [`projecta_local.py`](../../../scripts/projecta_local.py), [`project_workspace.py`](../../../apps/api/src/projecta_api/project_workspace.py), [`main.py`](../../../apps/api/src/projecta_api/main.py).
- Ontology version context: [`v0.5.1-compatibility-baseline.md`](../../architecture/v0.5.1-compatibility-baseline.md), [`ontology/m4-retrieval.ttl`](../../../ontology/m4-retrieval.ttl), [`bootstrap_fuseki.py`](../../../scripts/bootstrap_fuseki.py).
- Project workflow, evidence and correction-record field sources: [`structured_note.py`](../../../apps/api/src/projecta_api/structured_note.py), [`structured_note_store.py`](../../../apps/api/src/projecta_api/structured_note_store.py), [`structured_candidate_store.py`](../../../apps/api/src/projecta_api/structured_candidate_store.py), [`local_suggestion_store.py`](../../../apps/api/src/projecta_api/extraction/local_suggestion_store.py), [`correction_burden.py`](../../../apps/api/src/projecta_api/extraction/correction_burden.py), and [migration `0010`](../../../apps/api/alembic/versions/0010_correction_burden_events.py).
