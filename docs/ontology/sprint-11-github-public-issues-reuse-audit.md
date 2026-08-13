# Sprint 11 GitHub Public Issues Ontology Reuse Audit — S11-A05

**Status:** `HUMAN_APPROVED_PENDING_RELEASE_APPROVAL`

**Task:** S11-A05

**Semantic outcome:** `NO_ONTOLOGY_CHANGE_REQUIRED`

## Scope and semantic need

This audit evaluates whether public GitHub issues and issue comments require a
new Projecta class, property, controlled individual, SHACL shape, inference
rule, or ontology version. The use case needs source evidence, bounded exact
content, project scope, candidate review, provenance, actor hints, and replay
continuity. It does not require GitHub installation, cursor, provider ID,
rate-limit, retry, or UI state to become graph-queryable domain truth.

## Competency questions

| ID | Question | Existing answer |
| --- | --- | --- |
| CQ-GH-SRC-001 | Which project-scoped source artifact came from issue/comment observation `E`? | Existing project-scoped `Note`/`NoteItem` source mapping and operational event-to-source correlation |
| CQ-GH-EVID-001 | What bounded bytes, content hash, and evidence span support candidate `C`? | Existing evidence store, content metadata, offsets, and source/evidence chain |
| CQ-GH-CAND-001 | Which candidates came from imported issue/comment source `S`, and what is their review state? | Existing Candidate lifecycle, source mapping, and review activities |
| CQ-GH-PROV-001 | Which source, activity, model, and reviewer explain imported knowledge? | Existing PROV-O terms and confirmation/provenance lifecycle |
| CQ-GH-SCOPE-001 | Are source, candidate, evidence, and provenance records scoped to project `P`? | Existing project predicates, named graphs, authorization policy, and isolation shapes |
| CQ-GH-ACTOR-001 | Is a GitHub actor hint a confirmed Projecta `Person`? | Existing non-authoritative actor-hint boundary; no automatic identity merge |
| CQ-GH-OPS-001 | What cursor, revision, event, rate, or replay outcome was committed? | PostgreSQL connector operational repository and safe audit projections; not RDF |

The last question is intentionally operational. It is answerable without adding
an ontology term and prevents provider metadata from leaking into domain truth.

## Reuse mapping

| GitHub need | Released boundary | Classification |
| --- | --- | --- |
| Issue/comment source | `SourceArtifact`, `Note`, `NoteItem`, existing source mapping | Reuse |
| Bounded body/title/labels | Evidence content, hashes, and source offsets | Reuse |
| Imported semantic suggestion | Candidate/extracted/validated/pending-review lifecycle | Reuse |
| Human confirmation | Existing confirmation activity and candidate promotion | Reuse |
| Project isolation | Server policy, project predicates, named graph separation, isolation shapes | Reuse |
| Provider actor | Existing bounded actor/external-identity hint handling | Reuse without auto-merge |
| Provider issue/comment ID | PostgreSQL event identity and evidence metadata | Operational, outside RDF |
| `updated_at`, revision, cursor, replay | PostgreSQL connector run/inbox state | Operational, outside RDF |
| Repository owner/name and endpoint | Server-owned installation snapshot and safe UI projection | Operational, outside RDF |
| Rate limit, pagination, truncation, failure | Run/event outcome and audit projection | Operational, outside RDF |

## Semantic commitment gate

No new or materially changed semantic vocabulary is proposed. The concepts
under review classify as follows:

| Concept | Classification | Decision |
| --- | --- | --- |
| GitHub installation/type/capability | Operational/policy state | PostgreSQL/registry; no ontology term |
| Issue/comment observation | Source artifact observation | Reuse source/evidence lifecycle; no `GitHubIssue` or `GitHubComment` class |
| Provider issue/comment ID | External deduplication metadata | Opaque operational/evidence metadata; no new RDF property |
| Cursor/edit/replay/rate/truncation | Sync operational state | PostgreSQL/run outcome; explicitly outside RDF |
| GitHub login/user ID | Non-authoritative actor hint | Reuse hint boundary; no identity assertion or automatic `Person` merge |
| Imported requirement/task/decision | Candidate semantic proposal | Existing candidate lifecycle; never direct assertion |

Adding provider-shaped classes or properties would commit identity, lifecycle,
temporal, provenance, project, and migration semantics without a competency
question that the existing source/evidence/candidate model cannot answer.

## Positive examples

1. An issue body is stored as bounded evidence and mapped through the existing
   project-scoped source and candidate lifecycle.
2. An edited comment produces a new immutable source observation while the
   prior observation remains available through evidence/provenance history.
3. A reviewer confirms a candidate through the existing human-governed path;
   the connector never writes a `Requirement`, `Task`, or relation directly.
4. A GitHub login remains an actor hint unless an existing deterministic and
   human-confirmed identity flow resolves it.

## Counterexamples

- Creating `projecta:GitHubIssue`, `projecta:GitHubComment`, or
  `projecta:syncCursor` only to expose connector data is an ontology leak.
- Treating an issue title as a confirmed `Requirement` bypasses candidate and
  provenance governance.
- Writing provider URLs or raw IDs into RDF solely for deduplication commits
  an unreviewed identity meaning.
- Putting rate-limit, page, retry, or installation state in the inferred graph
  confuses operational memory with domain semantics.

## Alternatives considered

### Add a GitHub integration module now

Rejected for this slice. The connector needs operational bindings and source
evidence, not a durable provider domain model.

### Add `ExternalResource` and provider-specific properties now

Deferred. A future source catalog or cross-connector identity use case may
justify a governed proposal, but this import is answered by operational
metadata plus the existing source/provenance chain.

### Store the import as opaque JSON only

Rejected. That would create a parallel lifecycle and fail the existing source,
evidence, candidate, review, provenance, and project-context questions.

## Audit conclusion

`NO_ONTOLOGY_CHANGE_REQUIRED` is retained for the GitHub Public Issues slice.
No ontology Turtle, SHACL, rule, competency-query production fixture, version,
migration, or runtime RDF artifact is changed. Dependent implementation may
reuse the released semantic lifecycle. The project owner explicitly approved
this semantic outcome on 2026-08-13 for the exact issue/comment scope; release
approval remains a separate G2 decision.
If a later requirement makes external resources or connector identity durable
graph truth, implementation must pause and invoke the full
`projecta-evolve-ontology` semantic-commitment workflow.

## Review packet

- Business need: bounded public issue/comment source ingestion into Projecta
  memory without direct assertion.
- Competency gate: all required questions map to released source, evidence,
  candidate, provenance, identity-hint, project, or operational boundaries.
- Semantic commitment gate: no new class/property/individual/shape/rule is
  required.
- Impact: no ontology modules, SHACL, rules, RDF data, or version metadata
  change; only connector/API/operational artifacts will be added later.
- Human semantic approval: project owner confirmed that
  `NO_ONTOLOGY_CHANGE_REQUIRED` remains valid for this exact GitHub
  issue/comment scope on 2026-08-13.
- Release approval: intentionally separate and still pending at G2.
