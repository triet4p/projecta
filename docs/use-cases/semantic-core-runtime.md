# Semantic Core Runtime Use Case — Sprint 3 Slice Boundary

## 1. Purpose

This document fixes the executable boundary for the first Semantic Core slice.
It turns the released v0.2 lifecycle contract into four service operations:
validate a candidate, confirm a candidate, reject a candidate, and read an
allowlisted project-scoped view. It does not change ontology vocabulary,
SHACL shapes, or inference behavior.

The caller supplies a trusted project context. Authentication and authorization
are outside this sprint, but the runtime must reject requests whose resource or
graph does not belong to that context.

## 2. Shared Invariants

- The canonical graphs for project `<projectId>` are
  `/sources/`, `/candidates/`, `/asserted/`, `/inferred/`, and `/provenance/`.
- A candidate is read from and remains in the candidates graph. A confirmed
  candidate produces a distinct `projecta:KnowledgeItem` in the asserted graph.
- Source evidence is immutable. No operation copies a candidate into the
  asserted graph or writes a candidate to it.
- Every review outcome is a `prov:Activity` in the provenance graph and records
  the reviewer, decision, completion time, project, and input candidate.
- Assertion metadata uses released RDF reification (`rdf:Statement`) in the
  provenance graph. The corresponding direct triple remains in the asserted
  graph.
- The inferred graph is a reserved routing boundary; these operations do not
  run or materialize inference.
- All reads and writes execute with one server-derived project ID. A client
  never supplies a graph IRI or SPARQL update.

## 3. Validate Candidate

### Preconditions

- The candidate ID resolves only in the trusted project's candidates graph.
- The candidate has not reached a terminal review outcome.
- Released v0.2 ontology and all four released SHACL shape files are available
  to the Semantic Core.

### Success behavior and postconditions

1. The service constructs a validation dataset using the project's canonical
   graphs and runs the released SHACL shapes.
2. It returns a structured, deterministic list of conformance violations or a
   successful conformance result.
3. It records a validation activity in provenance and advances the candidate's
   current convenience status to `projecta:validated` only when it conforms.
4. It does not write to asserted or inferred graphs, even on success.

### Failure cases

- Unknown candidate or candidate from another project: not found in the
  trusted project scope; do not disclose whether it exists elsewhere.
- Non-conformant candidate: return violations; do not promote or change review
  state.
- Candidate already rejected or asserted: reject as an invalid lifecycle
  transition.
- Shape, ontology, or store failure: fail the operation without a partial
  lifecycle write.

### Expected graph diff

| Graph | Validation success | Validation failure |
|---|---|---|
| sources | unchanged | unchanged |
| candidates | current status becomes `validated` | unchanged |
| asserted / inferred | unchanged | unchanged |
| provenance | one validation `prov:Activity` | unchanged |

## 4. Confirm Candidate

### Preconditions

- The candidate is in the trusted project's candidates graph and conforms to
  the released shapes at decision time.
- The candidate is eligible for review (normally `pending-review` or
  `validated`); terminal states are not eligible.
- The reviewer identity is supplied by the trusted caller context.

### Success behavior and postconditions

Within one RDF write transaction, the service:

1. Re-reads and validates the candidate.
2. Creates a distinct asserted `projecta:KnowledgeItem` (or released subtype,
   such as `projecta:Requirement`) in the asserted graph, with project scope,
   `prov:wasDerivedFrom` the candidate, reviewer attribution, and required
   temporal metadata.
3. Adds RDF-reified provenance for each required assertion metadata triple.
4. Records a review activity with `projecta:reviewDecision projecta:confirmed`
   and an assertion activity in the provenance graph.
5. Advances the candidate's current convenience status to
   `projecta:asserted`.

The transaction commits only when every write and validation succeeds. The
candidate and source evidence remain available for audit.

### Failure cases

- Candidate fails revalidation: no asserted fact or provenance decision is
  committed.
- Candidate is already terminal or another decision wins first: return a
  lifecycle conflict; do not create another assertion.
- A generated asserted IRI collides, required provenance is incomplete, or a
  store write fails: roll back the complete transaction.
- Candidate or reviewer does not match the trusted project: reject before a
  graph mutation.

### Expected graph diff

| Graph | On successful confirm | On any failure |
|---|---|---|
| sources | unchanged | unchanged |
| candidates | current status becomes `asserted`; candidate retained | unchanged |
| asserted | one distinct KnowledgeItem and direct asserted facts | unchanged |
| inferred | unchanged | unchanged |
| provenance | review activity, assertion activity, and RDF statement metadata | unchanged |

## 5. Reject Candidate

### Preconditions

- The candidate is in the trusted project's candidates graph and is eligible
  for review.
- A non-empty, human-authored rejection reason and trusted reviewer identity
  are present.

### Success behavior and postconditions

Within one RDF write transaction, the service records a review activity with
`projecta:reviewDecision projecta:rejected`, records the reason, and advances
the candidate's current convenience status to `projecta:rejected`. It creates
no asserted fact and does not alter source or inferred data.

### Failure cases

- Missing rejection reason, invalid state transition, cross-project candidate,
  or a store failure: the complete rejection is rolled back.
- A concurrent confirmation wins: return a lifecycle conflict; do not append a
  competing rejection.

### Expected graph diff

| Graph | On successful reject | On any failure |
|---|---|---|
| sources | unchanged | unchanged |
| candidates | current status becomes `rejected`; rejection reason retained | unchanged |
| asserted / inferred | unchanged | unchanged |
| provenance | one rejected review activity | unchanged |

## 6. Project-Scoped Query

### Preconditions

- The caller has a trusted project context.
- The requested query name is on the Semantic Core allowlist; its parameters
  conform to the published contract.

### Success behavior and postconditions

The service binds the project and canonical graph IRIs internally, executes an
allowlisted current, history, or evidence query, and returns only the selected
projection. Querying does not mutate any graph.

### Failure cases

- Unknown query name or unsupported parameter: reject without evaluating
  SPARQL.
- A candidate, fact, source, or graph identifier is outside the trusted
  project: return scope-safe not-found or forbidden behavior defined by the API
  contract.
- Store failure: return a translated service error without leaking a raw SPARQL
  query or endpoint details.

## 7. Deliberate Non-Goals

- No raw SPARQL Update or arbitrary read SPARQL endpoint.
- No authentication provider, role model, UI, connector, LLM extraction, or
  business inference.
- No cross-project sharing, candidate deduplication policy, retraction, or
  supersession runtime in this slice.
- No semantic term, shape, or rule changes.

## 8. Required Human Review: Current Status Representation

The released `CandidateShape` requires exactly one `candidateStatus`, while
the Sprint 2 narrative says state history must not be overwritten. This runtime
slice treats `candidateStatus` as the released convenience denormalization and
records authoritative immutable history in provenance activities. Updating the
single current-status triple therefore replaces only that denormalized value;
it never deletes provenance history.

**S3-03 human approval:** Approved on 2026-07-29. The operational
interpretation is accepted for the Sprint 3 implementation. A future change to
the released ontology/shape contract still requires governed ontology review.
