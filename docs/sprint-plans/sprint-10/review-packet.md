# Sprint 10 G1 Architecture, Security, and Semantic Review Packet

## Status

`HUMAN_APPROVED`

**Scope:** S10-01 through S10-09 only

**Approval task:** S10-10

Human approval was recorded in the project task conversation on 2026-08-10.
Implementation tasks S10-11 onward are authorized within the boundaries below.
No new ontology vocabulary is approved by this artifact.

## Review outcome requested

Approve or revise the complete pre-implementation boundary for the first
governed connector vertical slice:

```text
server-authorized JSON/Mock adapter
  → canonical-event.v1
  → PostgreSQL operational state
  → bounded immutable evidence
  → existing Note/NoteItem + candidate/provenance lifecycle
  → typed API and later Connections UI
```

The connector is inbound-only, deterministic, project-scoped, bounded,
single-attempt, explicit-retry, replay-safe, and incapable of direct assertion.

## Completed discovery artifacts

| Task | Artifact | Result |
| --- | --- | --- |
| S10-01 | [v0.4.0 compatibility baseline](F:/ai-ml/projecta/docs/architecture/v0.4.0-compatibility-baseline.md) | Public routes, projections, versions, Compose, release evidence, and validation totals frozen |
| S10-02 | [JSON/Mock connector use case](F:/ai-ml/projecta/docs/use-cases/json-mock-connector.md) | Actors, preconditions, seven acceptance journeys, fixture, counterexamples, outcomes, non-goals |
| S10-03 | [Canonical event contract](F:/ai-ml/projecta/docs/architecture/canonical-event-contract.md) | `canonical-event.v1`, identity/hash, bounds, validation, safe problems |
| S10-04 | [Connector adapter contract](F:/ai-ml/projecta/docs/architecture/connector-contract.md) | Registry, capabilities, install validation, pull/fetch/identity hint, cursor, cancellation/deadline, terminal errors |
| S10-05 | [Connector authorization contract](F:/ai-ml/projecta/docs/architecture/connector-authorization.md) | Server principal, project policy, operation matrix, revisions, safe 403/404, secret boundary |
| S10-06 | [Connector threat model](F:/ai-ml/projecta/docs/architecture/connector-threat-model.md) | Trust zones, 20 threats, controls, security invariants, abuse/failure matrix, residual risks |
| S10-07 | [Connector operational storage contract](F:/ai-ml/projecta/docs/architecture/connector-operational-storage.md) | PostgreSQL logical schema, project predicates, transactions, replay/retry, retention, migration, backup/recovery |
| S10-08 | [Connector evidence storage contract](F:/ai-ml/projecta/docs/architecture/connector-evidence-storage.md) | Evidence port, immutable/content-addressed writes, bounded reads, digest/media/retention/isolation rules |
| S10-09 | [Ontology reuse-gap audit](F:/ai-ml/projecta/docs/ontology/sprint-10-connector-reuse-gap.md) | Proposed `NO_ONTOLOGY_CHANGE_REQUIRED`; status remains pending human review |

Task summaries are in [the Sprint 10 artifacts directory](F:/ai-ml/projecta/docs/sprint-plans/sprint-10/artifacts/).

## Proposed boundary decisions

### Compatibility

- Preserve the v0.4.0 annotated release target
  `0b36a3eefdd7efa126e44de25a3653f3ebc30c27`.
- Preserve released typed routes, opaque project/graph/knowledge handles,
  candidate/asserted/inferred/source/provenance separation, and browser/API
  trust boundaries.
- Add PostgreSQL connector state and evidence storage only as additive new
  boundaries; do not rewrite existing semantic data or local workflows.

### Connector and event

- Register only explicit allowlisted adapter types and finite capabilities.
- Use `canonical-event.v1` with server-derived project/installation scope,
  stable event identity, canonical body hash, evidence content hash, bounded
  actor hint, external reference, timestamp, and source event type.
- Treat event type/external reference/actor hint as ingestion/source metadata,
  never as a domain assertion or authorization input.
- One adapter call and one absolute deadline per run; no hidden retry.

### Authorization and secrets

- Resolve a server-owned principal, project membership, connector-admin action,
  installation revision, capability, and idempotency before adapter execution.
- Keep the local experience adapter for local/test only and fail closed in
  production mode.
- Store only opaque SecretStore references; the JSON/Mock adapter requires no
  real credential.
- Use safe not-found/forbidden mapping that does not reveal another project's
  installation, event, evidence, cursor, or run.

### Operational and evidence state

- PostgreSQL owns installations, inbox/idempotency, runs/attempts, cursors,
  retry lineage, dead letters, audit, and read projections.
- Evidence storage owns raw bytes with project-scoped content addressing,
  digest verification, bounded streaming, retention metadata, and no
  list-all/arbitrary-path capability.
- Fuseki/TDB2 owns semantic graphs; operational connector state never enters
  RDF.
- Cursor advances exactly once only after evidence and Semantic Core commit;
  failures leave cursor and semantic state unchanged or explicitly
  reconcilable.

### Ontology

- Proposed outcome: `NO_ONTOLOGY_CHANGE_REQUIRED`.
- Reuse released `Note`, `NoteItem`, source/evidence offsets, project scope,
  `Candidate`/v0.4 candidate subclasses, lifecycle, PROV-O, named graphs, and
  isolation shapes.
- Keep installation/event/cursor/retry/dead-letter/UI state and operational
  external references outside the ontology.
- If G1 requires a durable `ExternalResource`, connector provenance, or
  identity vocabulary term, stop dependent semantic work and open a new
  `$projecta-evolve-ontology` proposal for that exact term.

## Validation evidence

Passed:

- v0.4.0 release contract: `uv run --no-project python scripts/check_release_contract.py --tag v0.4.0`.
- Five Sprint 10 discovery contract test files: 10 tests passed.
- Sprint 10 ontology reuse-gap test: 2 tests passed.
- Canonical Compose ontology runner: `Result: 140/140 checks passed`.
- `git diff --check`.

Not claimed as Sprint 10 implementation evidence:

- API/PostgreSQL/migration/repository/adapter/UI/recovery tests, because those
  components are not implemented yet.
- Direct host ontology validation, because `riot` is not installed on the host;
  the canonical Compose runner supplied the actual ontology validation.

## Human decisions requested at G1

Please explicitly approve or revise:

- [x] The v0.4.0 compatibility baseline and additive-only constraint.
- [x] The JSON/Mock use case and all seven acceptance journeys.
- [x] `canonical-event.v1`, identity/body hash, bounds, event allowlist, and
  safe validation/error behavior.
- [x] The provider-neutral adapter port, finite capabilities, cursor,
  cancellation/deadline, and single-attempt/no-hidden-retry rule.
- [x] The server-owned principal/policy seam, local-mode production rejection,
  secret-reference boundary, and operation matrix.
- [x] The threat model, controls, residual risks, and required security gates.
- [x] The PostgreSQL operational schema, cross-store completion/reconciliation,
  retention, migration, backup, and restore boundary.
- [x] The evidence port, immutable/content-addressed policy, limits, isolation,
  retention/deletion, and restore boundary.
- [x] The ontology reuse outcome `NO_ONTOLOGY_CHANGE_REQUIRED`.
- [x] The first connector runtime location: inside the Application API process
  or a separate deployable runtime.
- [x] Authorization to begin S10-11 implementation after these decisions are
  recorded.

## Human approval record

- **Approved:** 2026-08-10, by the human reviewer in the project task
  conversation (“Approve for all, please continue with B: S10-11 -> S10-22”).
- **Runtime placement:** inside the existing Application API process, behind
  provider-neutral connector ports.
- **Approval boundary:** all listed G1 architecture, security, persistence,
  evidence, semantic-reuse, and implementation-start decisions are approved;
  no production identity provider, real external connector, new ontology term,
  or G2/G3 release authorization is implied.

## Stop conditions

Work must stop before S10-11 if G1 is not explicitly approved. Work must also
stop immediately if:

- the ontology reuse outcome changes to a new durable term;
- a contract requires browser authority, arbitrary connector execution, raw
  payload exposure, hidden retry, or direct assertion;
- the runtime placement or production authentication boundary is materially
  changed without a new decision;
- any required security/isolation/recovery invariant cannot be preserved.

S10-10 is satisfied by the approval record above. Future ontology changes,
production authentication/secret-manager changes, and G2/G3 release decisions
remain separate human gates.
