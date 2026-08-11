# Sprint 10 Connector Ontology Reuse-Gap Audit

## Status

`APPROVED_FOR_RELEASE`

**Semantic outcome:** `NO_ONTOLOGY_CHANGE_REQUIRED`

**Task:** S10-09

**Scope:** Connector source provenance, canonical event metadata, external
references, actor hints, evidence, candidate lifecycle, and project isolation
for the deterministic JSON/Mock vertical slice.

Human approval of the reuse outcome was recorded at G1 on 2026-08-10. This
packet does not publish an ontology version, change runtime vocabulary, or
migrate RDF data.

## Semantic outcome

The released ontology and Semantic Core lifecycle are sufficient for Sprint 10
when connector input is treated as bounded source/evidence data and operational
metadata:

```text
canonical event + raw evidence
  → project-scoped Note / NoteItem source
  → evidence offsets + content hash + provenance
  → reviewable Candidate lifecycle
  → existing human confirmation boundary
```

No new Projecta class, object property, datatype property, controlled
individual, SHACL shape, inference rule, or migration is required for this
vertical slice.

The following concepts remain outside the ontology:

- connector installation, connector type, capability snapshot;
- canonical event ID/body hash and event type;
- sync run, single attempt, cursor, idempotency key, retry lineage;
- dead-letter and operational audit state;
- opaque evidence-store reference, storage locator, retention state;
- external resource reference used for ingestion deduplication;
- actor hint used for source attribution/candidate review;
- UI status, polling state, operation deadline, and public projection fields.

These are operational state, source metadata, evidence metadata, retrieval
metadata, or UI projections. They belong in PostgreSQL, the evidence store,
safe telemetry, or typed Application API DTOs according to the S10-03–08
contracts. They must not become RDF domain facts merely because they appear in
a connector payload.

## Justification

### Use-case and governance need

Sprint 10 needs to import bounded external content into the existing project
memory without allowing an adapter or raw payload to create an assertion. The
semantic questions are about source content, evidence, provenance, candidate
review, project scope, and the eventual human decision—not about operational
cursor/retry/UI state as domain meaning.

This follows the initialization principles that ontology is shared domain
meaning, source/evidence is distinct from truth, candidates are distinct from
asserted/inferred knowledge, and operational memory remains in PostgreSQL.

### Released terms reused

| Connector need | Released semantic reuse | Boundary |
| --- | --- | --- |
| Project scope | `projecta:Project`, `projecta:belongsToProject`, project-named graphs, isolation shapes | Semantic Core and authorization enforce scope; event scope is server-derived |
| Imported source | `projecta:SourceArtifact`, `projecta:Note`, `projecta:NoteItem`, `projecta:hasNoteItem`, `projecta:isItemOf` | Connector content becomes source material, not a fact |
| Source author/context | `projecta:authoredBy`, `projecta:Person`, `projecta:recordedAt` | Actor hint is not an authenticated principal or automatic identity merge |
| Typed source items | Released `projecta:NoteItemType` individuals and `projecta:hasItemType` | Allowlisted source classification only |
| Exact source evidence | `projecta:rawText`, `projecta:contentText`, `projecta:evidenceStartOffset`, `projecta:evidenceEndOffset` | Exact offsets and content hash are source/evidence controls |
| Candidate review | `projecta:Candidate`, v0.4 `EntityCandidate`, `RelationCandidate`, `EntityLinkCandidate`, lifecycle statuses and review activities | Imported content remains reviewable proposal data |
| Provenance | PROV-O `prov:Entity`, `prov:Activity`, `prov:Agent`, `prov:wasDerivedFrom`, `prov:wasGeneratedBy`, `prov:wasAttributedTo`, `prov:used` | Connector run/event details can stay operational while semantic derivation remains queryable |
| Assertion boundary | Existing candidate → confirmation → asserted lifecycle and named graph separation | Connector never writes asserted/inferred facts directly |
| Cross-project safety | Existing project predicates, named graph routing, isolation shapes, same-project candidate/link validation | Authorization is still required; named graphs are defense in depth |

No released term was found for `Connector`, `ConnectorType`, `ExternalResource`,
`ExternalIdentity`, `SourceSystem`, `Capability`, or connector operational
state in the current ontology tree. Their absence is intentional for this
slice: the initialization document lists them as a possible future integration
module, but the Sprint 10 contract classifies the first-connector instances as
operational/provider boundary data rather than durable domain vocabulary.

## Competency questions

These questions test the connector semantic boundary without adding new terms.

| ID | Competency question | Reuse answer |
| --- | --- | --- |
| CQ-CONN-SRC-001 | Which project-scoped source Note/NoteItem was created from imported event `E`? | Operational event/inbox links `E` to the source operation; Semantic Core answers through the existing Note/NoteItem source graph, project predicate, raw text, and exact evidence offsets. |
| CQ-CONN-EVID-001 | What source bytes and exact spans support imported candidate `C`? | Existing evidence metadata, offsets, content text/hash, `prov:wasDerivedFrom`, and candidate source chain answer it. Raw bytes remain in evidence storage. |
| CQ-CONN-PROV-001 | Which connector operation/actor/time produced source artifact `S`? | Operational run/event/audit records retain connector-specific identity; Semantic Core reuses `prov:Activity`, `prov:used`, `prov:wasGeneratedBy`, `prov:wasAttributedTo`, and `recordedAt` for semantic derivation. |
| CQ-CONN-CAND-001 | Which candidates came from imported source `S`, and what is their review state? | Existing `Candidate` subclasses, lifecycle statuses, source evidence, and review activities answer it. |
| CQ-CONN-SCOPE-001 | Are imported source, candidate, evidence, and provenance records in project `P` only? | Existing `belongsToProject`, named graph routing, isolation shapes, and same-project validation answer it. |
| CQ-CONN-REVIEW-001 | Was imported content confirmed, rejected, or left pending? | Existing candidate lifecycle and provenance review activities answer it without connector-specific status vocabulary. |
| CQ-CONN-EXT-001 | Which external reference was used to deduplicate source event `E`? | This is an operational ingestion question answered by the PostgreSQL inbox/run projection and safe audit metadata. It does not require a domain RDF term for the first slice. |
| CQ-CONN-IDENT-001 | Was an external actor hint resolved to a Projecta Person? | The first slice retains the hint as source/operational data and abstains from automatic identity merge. A future durable identity-link question requires its own semantic review. |

The last two questions deliberately demonstrate the boundary: an operational
query need does not automatically justify an ontology class or property.

## Semantic commitment gate

No new or materially changed class/property is proposed. Therefore the
mandatory semantic-commitment interview is not applicable to a vocabulary
addition. The classification review is still recorded:

| Concept under review | Classification | Primary outcome |
| --- | --- | --- |
| Connector installation/type/capability | Operational/policy state | Keep in PostgreSQL/registry; no ontology term |
| Canonical event identity/type/scope | Canonical ingestion contract | Keep in operational inbox/event model; no ontology term |
| External reference/content hash | Evidence/operational metadata | Keep in evidence metadata and PostgreSQL; reuse source/provenance linkage |
| Actor hint/external identity hint | Source hint/candidate input | Do not assert or merge; no new identity vocabulary in Sprint 10 |
| Sync run/attempt/cursor/retry/dead-letter | Operational state | Keep in PostgreSQL; explicitly forbidden from RDF |
| Note/NoteItem/source evidence | Released source semantics | Reuse existing terms and shapes |
| Candidate/review/provenance | Released lifecycle semantics | Reuse v0.4 candidate/lifecycle/PROV-O contracts |
| Connector UI/status/projection | Application projection | Keep in typed API/UI DTOs; no ontology term |

If a later requirement makes `ExternalResource`, connector provenance identity,
or external identity a durable cross-project domain entity, stop dependent
semantic implementation and run the full semantic-commitment interview and
human review packet for that exact term. This audit does not pre-approve that
future change.

## Positive and boundary examples

### Positive reuse examples

1. A JSON/Mock `source.created` event stores raw evidence and maps its bounded
   content to one project-scoped `Note` with `NoteItem`s, exact offsets,
   `recordedAt`, and source provenance.
2. The same source produces a v0.4 `Requirement` candidate with evidence and a
   pending-review lifecycle; a human may later confirm it through existing
   Semantic Core operations.
3. A replay uses PostgreSQL event identity/body hash and returns the original
   outcome without creating another Note, Candidate, or provenance activity.

### Counterexamples

1. Creating `projecta:ConnectorInstallation` or `projecta:syncCursor` only to
   make PostgreSQL rows queryable in RDF is operational-state leakage.
2. Writing `projecta:externalReference` on a Note without a committed domain
   meaning, identity criterion, lifecycle, project policy, and provenance
   semantics is an unreviewed vocabulary addition.
3. Mapping an actor display name directly to `projecta:Person` is an identity
   merge and violates the existing deterministic-match/human-confirmation
   boundary.
4. Writing imported content directly as `Requirement`, `Task`, `implements`,
   or inferred facts bypasses candidate/review/provenance lifecycle.

## Alternatives considered

### Add an integration ontology module now

Rejected for Sprint 10. The first deterministic connector does not need a
durable domain representation of installation, cursor, retry, dead-letter,
capability, or UI state. Adding these terms would commit identity/lifecycle,
temporal, project, provenance, and migration semantics without a competency
question requiring them.

### Add `ExternalResource` and `externalReference` terms to Notes

Deferred. The first slice only needs external references for operational
deduplication, evidence lookup, and audit. PostgreSQL/evidence projections
answer those questions without exposing provider identity as domain truth. A
future cross-connector entity-resolution or source-catalog use case may justify
a separate proposal.

### Keep imported content as opaque application JSON

Rejected. That would fail the existing source/evidence, Note/NoteItem,
candidate-review, provenance, Graph, and Review Queue competency questions and
would create a second semantic lifecycle.

### Reuse only generic `Candidate` without connector/source mapping

Rejected. The existing source Note/NoteItem and exact evidence chain are needed
for reviewable imported content; reuse means mapping through the released
lifecycle, not dropping provenance into an opaque operational blob.

## Artifact diff

No production ontology artifact is changed.

Created:

- `docs/ontology/sprint-10-connector-reuse-gap.md` — this review packet.
- `scripts/tests/test_sprint10_ontology_reuse_gap.py` — deterministic audit
  completeness test.
- `docs/sprint-plans/sprint-10/artifacts/task_S10-09_summary.md` — task record.

Not created or changed:

- no ontology Turtle module;
- no SHACL shape;
- no inference rule;
- no competency-query production fixture;
- no ontology version/migration/deprecation artifact;
- no runtime ontology or asserted RDF data mutation.

## Validation evidence

### Automated checks

- `rg` search across `ontology/`, `docs/ontology/`, and initialization docs for
  connector/external vocabulary and existing source/provenance terms — passed;
- current ontology source, source/evidence/isolation shapes, v0.4 candidate
  artifacts, and approved structured-note packet were manually inspected;
- `uv run --script scripts/validate_ontology.py ontology` — required to pass
  the released ontology suite; this is a regression check, not a new Sprint 10
  ontology check;
- `uv run --no-project python -m unittest discover -s scripts/tests -p
  "test_sprint10_ontology_reuse_gap.py"` — required to pass;
- `git diff --check` — required to pass.

### Manual semantic inspection

The reuse matrix above confirms that source, evidence, candidate, lifecycle,
provenance, project isolation, and human review semantics already exist. The
operational classification prevents connector state from entering RDF.

## Compatibility and risk

### Impact

- Ontology modules: no import/hierarchy/property change.
- SHACL: existing source/evidence/candidate/isolation shapes remain canonical.
- Rules/inference: no connector operational state is used as a rule fact.
- SPARQL/CQs: released queries remain valid; connector-specific operational
  queries belong to PostgreSQL/read projections.
- Existing RDF data: no migration, backfill, deprecation, or rewrite.
- Semantic Core: reuse released Note/NoteItem/candidate/provenance mutation path.
- API/connectors/UI: connector-specific DTOs and state remain typed operational
  contracts, not ontology terms.
- Permissions/isolation: project scope remains server policy plus named graphs;
  named graphs alone do not authorize access.
- Provenance: source/evidence and review activities remain linked through
  existing PROV-O terms.

### Residual risks

- A future requirement for graph-queryable external resource identity may expose
  a real semantic gap.
- Actor hints may remain ambiguous and require explicit review.
- Exact connector-source mapping fields and operational-to-semantic correlation
  must be implemented without leaking event IDs or storage details.
- The no-change outcome is human-approved for the Sprint 10 release boundary.

## Unresolved questions

These are the only questions requiring human semantic/architecture authority:

1. Does G1 agree that external references remain operational/evidence metadata
   for Sprint 10 rather than a new RDF property/class?
2. Does G1 agree that actor hints remain non-authoritative and that identity
   merge is outside the JSON/Mock slice?
3. Does G1 agree that imported content must reuse Note/NoteItem/candidate/
   provenance and cannot create direct assertions?
4. If any answer is no, which exact competency question and domain meaning
   require a new term, and should dependent semantic work stop for a new
   `$projecta-evolve-ontology` proposal?

## Human actions requested

- [x] Approve the `NO_ONTOLOGY_CHANGE_REQUIRED` semantic outcome.
- [x] Approve reuse of released Note/NoteItem, evidence, candidate, lifecycle,
  project, isolation, and PROV-O semantics.
- [x] Approve keeping connector installation/event/cursor/retry/dead-letter/UI
  state in operational storage rather than RDF.
- [x] Approve keeping external references and actor hints operational/source
  metadata without a new Projecta vocabulary term.
- [x] Authorize dependent semantic implementation after G1 under these exact
  boundaries.

Approval is limited to the recorded no-change reuse boundary. Sprint 10
approval does not pre-approve a future ontology vocabulary change.
