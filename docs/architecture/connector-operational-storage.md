# Connector Operational Storage Contract — Sprint 10

**Status:** `G1_APPROVED_IMPLEMENTATION`

**Task:** S10-07

**Storage:** PostgreSQL for connector operational state and read projections

## Boundary

PostgreSQL owns connector workflow state, idempotency, cursor, retry lineage,
dead-letter metadata, authorization/audit indexes, and safe read projections.
It is not the semantic source of truth. Fuseki/TDB2 remains the owner of source,
candidate, asserted, inferred, and provenance graphs. The evidence store owns
raw source bytes.

Connector operational rows never become RDF facts. They do not model
Requirement, Task, connector UI state, or semantic lifecycle vocabulary.

## Logical schema

The v1 logical schema is project-scoped and uses server-generated internal keys.
Public API responses use opaque handles and bounded DTOs only.

### `connector_installations`

One project-scoped installation configuration and policy snapshot.

Required fields:

- internal installation key;
- project foreign key;
- allowlisted `connector_type`;
- capability snapshot and contract version;
- opaque secret references only;
- enabled/disabled state;
- optimistic `revision`;
- created/updated/enabled/disabled timestamps;
- safe actor/audit references.

Constraints:

- project and installation identity are unique together;
- connector type is allowlisted and cannot be silently changed across a
  revision where the contract forbids it;
- capability snapshot is finite and revalidated against the registry;
- raw credentials, provider payloads, filesystem paths, and arbitrary config
  blobs are forbidden columns;
- all reads and writes include the project predicate.

### `connector_event_inbox`

One canonical event identity/body outcome per project and installation.

Required fields:

- internal inbox key;
- project and installation foreign keys;
- canonical `event_id`, `connector_type`, and external-reference digest/summary;
- canonical body hash and evidence content hash;
- opaque evidence reference;
- accepted/processing/terminal outcome;
- source/candidate operation idempotency key;
- first-seen/claimed/completed timestamps;
- safe correlation and run references;
- revision.

Constraints:

- unique `(project, installation, event_id)` identity;
- body-hash mismatch is a typed conflict and never overwrites the original;
- no raw event body or secret is stored in this table;
- external references are bounded safe summaries or digests, never arbitrary
  provider payloads;
- project/installation foreign keys prevent cross-project orphan rows.

### `connector_sync_runs`

One explicit user/operator-requested sync operation and exactly one terminal
outcome.

Required fields:

- internal run key and public opaque run handle mapping;
- project/installation foreign keys;
- operation idempotency key;
- requested connector capability;
- installation revision snapshot;
- run state and terminal outcome;
- source/event/evidence counters;
- start/deadline/terminal timestamps;
- correlation IDs;
- explicit retry parent run reference, when applicable;
- safe failure class/detail summary.

Finite states:

```text
requested → running → succeeded
                    → replayed
                    → failed
                    → cancelled
                    → dead-lettered
```

`requested` and `running` are non-terminal. Every run has exactly one terminal
state. There is no implicit `retrying` state and no automatic child run.

### `connector_sync_attempts`

One adapter attempt record per sync run. An explicit retry creates a new run
and one new attempt linked to the failed parent; SDK/HTTP/worker retries never
create hidden attempts.

Required fields:

- run and installation/project foreign keys;
- attempt number fixed to `1` for the run;
- adapter type/capability snapshot;
- start/deadline/terminal timestamps;
- safe adapter outcome/error class;
- bounded event/byte counters;
- no raw request/response payload.

Unique `(run_id, attempt_number)` proves single-attempt execution.

### `connector_cursors`

One opaque source checkpoint per project/installation/connector type.

Required fields:

- installation/project foreign keys;
- opaque cursor value or encrypted/opaque reference according to the approved
  adapter boundary;
- cursor revision;
- last committed event/run reference;
- updated timestamp;
- optimistic version.

The cursor table never stores a parsed provider ID as public data. A cursor is
advanced only after the corresponding source/evidence and Semantic Core
commit, exactly once. It remains unchanged on validation, conflict, storage,
Core, cancellation, timeout, dead-letter, or rollback failure.

### `connector_idempotency_keys`

Optional normalized index for operation-level idempotency. It records only:

- project/installation scope;
- operation kind;
- opaque key digest;
- canonical request/body digest;
- first result/run reference;
- created/expired timestamps.

The key is never returned as a credential or used as a browser authority. A
same key with a different canonical request returns a conflict and preserves
the original result.

### `connector_dead_letters`

Sanitized terminal failure metadata for an event/run that cannot complete.

Allowed fields:

- project/install/run/event opaque internal references;
- allowlisted failure class and safe bounded detail;
- correlation IDs;
- retryability and explicit next action;
- created/updated/terminal timestamps;
- revision.

Forbidden fields:

- raw event/evidence payload;
- secret, token, credential, or secret reference;
- stack trace or SQL;
- RDF IRI, graph name, TDB2 path, filesystem path;
- unbounded provider error object;
- cross-project identifiers.

### `connector_audit_events`

An indexed, append-oriented record of authorized decisions and terminal
outcomes. It stores safe action, decision, project-safe scope, actor-safe
attribution, connector type, revision, correlation, and timestamp. It does not
become an RDF provenance graph and does not duplicate raw payload/evidence.

### Read projections

Installation, last-run, cursor, and dead-letter summaries may be projected into
bounded PostgreSQL read models. They are rebuildable from operational rows,
never writable by the browser, and must carry projection revision/freshness.

## Foreign keys and project predicates

Every connector table includes a project scope or reaches one through a
foreign key. Repository methods must include project scope in every query,
including lookup by an opaque handle, run, event, cursor, idempotency key, or
dead-letter reference.

Recommended constraints:

- installation `(project_id, installation_id)` is the parent scope for all child
  rows;
- child foreign keys include the project key where PostgreSQL composite keys
  are used to prevent mismatched project/installation joins;
- unique keys include project/installation scope where identity is local;
- deletes are restricted or explicitly retention-governed, never cascaded from
  a browser request into evidence/semantic data;
- public handles are resolved only after authorization and revision checks.

## Transaction semantics

### Installation mutation

Create/update/enable/disable runs in one PostgreSQL transaction:

1. authorize server principal and project scope;
2. lock or compare the expected installation revision;
3. validate finite connector/capability/secret-reference configuration;
4. write the new revision and audit decision;
5. commit once.

A stale revision produces no mutation and no adapter call.

### Event claim and replay

Inbox claim is one bounded transaction:

1. verify project/installation/run scope;
2. insert the canonical identity/body hash if absent;
3. if present, return replay for the same body hash or conflict for a mismatch;
4. associate the winning run and safe correlation;
5. commit the claim without advancing the cursor.

Concurrent claims have one winner. A loser cannot create a second semantic
operation or overwrite the winning body/outcome.

### Source/evidence/Core/cursor completion

PostgreSQL, evidence storage, and RDF are separate stateful boundaries and do
not share one ACID transaction. The explicit completion protocol is:

```text
claim inbox/run
  → store/verify bounded evidence
  → call Semantic Core with one idempotency operation
  → receive durable source/candidate/provenance commit
  → commit terminal run/inbox outcome and cursor in PostgreSQL
```

Rules:

- PostgreSQL never marks success or advances the cursor before Core success.
- Semantic Core receives a stable operation idempotency key so a recovery
  finalizer can verify/reuse a committed source without duplicating it.
- If evidence succeeds but Core fails, the run is failed/dead-lettered, the
  cursor is unchanged, and the evidence reference remains bounded and subject
  to retention/reconciliation policy.
- If Core succeeds but the final PostgreSQL transaction fails, the run remains
  explicitly reconcilable; recovery verifies the Core idempotent outcome before
  committing the cursor and terminal row. It does not issue a second semantic
  mutation.
- Any uncertainty is failed/reconcilable, never reported as success.

The final cross-store recovery protocol and tooling are release requirements
for S10-56–59 and must not be replaced with a best-effort cursor update.

## Retry and replay semantics

- A successful same-body event replay returns the original outcome and cursor;
  it does not create a source/candidate duplicate.
- A failed run may be explicitly retried only with authorization, expected
  failed-run revision, a new operation idempotency key, and parent linkage.
- A retry is a new run with one attempt; there is no automatic loop.
- Retry cannot change project, installation, event identity, or canonical body.
- A body mismatch is a conflict, not a retry.
- The original run and all retry lineage remain auditable.

## Retention and deletion

Proposed defaults require G1 approval and must be configurable without widening
public reads:

- installations and revisions: retain while project configuration exists;
- successful run/inbox/cursor metadata: retain for operational audit period;
- failed/dead-letter metadata: retain through review/retry window;
- idempotency keys: retain at least for the replay/conflict safety window;
- audit records: retain according to the project/operator audit policy;
- raw evidence: governed by the separate evidence contract, content hash, and
  retention metadata.

Deletion is a server-authorized, audited retention operation. It never allows a
browser to delete arbitrary rows/evidence or erase semantic provenance. Any
purge must preserve the ability to explain the terminal outcome and must be
safe for backup/restore/replay policy.

## Migration contract

PostgreSQL connector schema changes use a pinned, versioned migration entry
point, separate from concurrent API replica startup:

- empty bootstrap is deterministic and fail-explicit;
- repeated migration is idempotent;
- each migration records its version and checksum;
- migrations use transactional DDL where supported;
- destructive/irreversible changes require an explicit reviewed boundary,
  backup evidence, and rollback/forward-fix plan;
- API startup does not race migrations;
- a failed migration returns nonzero and does not claim readiness;
- application code remains compatible with the previous schema during a
  controlled upgrade where required.

The migration runner, PostgreSQL Compose dependency, schema implementation, and
lifecycle tests are S10-11–19 work after G1.

## Backup, restore, and rollback

The operational database backup must include connector schema/data needed to
verify installations, inbox outcomes, run/retry lineage, cursors, dead letters,
idempotency, and audit. It must be version-checked against the migration level.

Restore is always into an isolated clean stack for validation. It must verify:

- installation revisions and enabled states;
- event identity/body hashes and terminal outcomes;
- cursor values and run/retry lineage;
- sanitized dead letters/audit;
- compatibility with the evidence volume and Semantic Core operation keys;
- replay-after-restore does not duplicate source, candidate, assertion, run
  outcome, or cursor advancement.

Rollback of a failed operation means restoring the previous operational
transaction/revision or recording a safe terminal failure. It never rewinds a
released semantic assertion or silently decrements a source cursor without
recovery evidence.

## Observability and safety

Operational telemetry may include safe boundary, operation, connector type,
project-safe scope, outcome, duration, count, replay, and revision fields. It
must not include raw payload, secret, credentials, SQL, RDF, graph/path,
provider object, or stack trace. Every start has one terminal event, and a
failed dead-letter persistence path must itself produce a safe correlated
failure without hiding the original outcome.

## G1 decisions required

Human approval at S10-10 must confirm the logical table boundary, cross-store
completion protocol, retention defaults, migration/backup ownership,
reconciliation behavior, and the rule that connector operational state remains
outside RDF.
