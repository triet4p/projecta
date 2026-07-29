# Sprint 3 Review Packet — Executable Semantic Core

**Status:** HUMAN APPROVED

**Human approval:** 2026-07-30

**Scope:** Sprint 3 tasks S3-01 through S3-20. This packet records verified
implementation evidence and the decisions still required for S3-21; it does
not itself approve M1.

## Review Request

The reopened runtime and HTTP-boundary blockers have been implemented and
verified. This packet requests human M1 approval; it does not approve M1 by
itself.

## Delivered Boundary

The Semantic Core routes every project lifecycle graph through a validated
`ProjectId`: `sources`, `candidates`, `asserted`, `inferred`, and `provenance`.
It provides typed in-process services for candidate validation, confirmation,
rejection, current knowledge, candidate history, and evidence lookup. No
service accepts a graph IRI, raw RDF update, or SPARQL update from a caller.

The approved public contract remains
[Semantic Core API Contract](../../architecture/semantic-core-api.md). The
runtime behavior is fixed by
[Semantic Core Runtime Use Case](../../use-cases/semantic-core-runtime.md).

## API Examples

The contract defines these domain-safe operations:

| Operation | Contract request | Result |
|---|---|---|
| Validate | `POST /v1/candidates/{candidateId}/validations` | Shape conformance or structured `CANDIDATE_INVALID` problem. |
| Confirm | `POST /v1/candidates/{candidateId}/confirmations` with `Idempotency-Key` | One asserted Requirement plus review and reified provenance. |
| Reject | `POST /v1/candidates/{candidateId}/rejections` with a human reason and key | One rejection review activity; no asserted item. |
| Read | Current, history, and evidence allowlist endpoints | Only records visible through the trusted project context. |

`ApiProblem` and `ApiErrorTranslator` return stable, sanitized problem fields:
`type`, `title`, `status`, `code`, `detail`, and `requestId`. Tests verify that
graph and Fuseki implementation details are not exposed.

## Lifecycle Evidence

| Graph | Confirm | Reject | Failure or conflict |
|---|---|---|---|
| candidates | Replaces convenience status with `asserted`; candidate remains auditable. | Replaces status with `rejected` and retains the reason. | No mutation. |
| asserted | Creates one distinct KnowledgeItem/Requirement. | Unchanged. | No mutation. |
| provenance | Creates review activity and `rdf:Statement` metadata. | Creates reviewer-attributed rejected activity. | No mutation. |
| inferred | Unchanged. | Unchanged. | Unchanged. |
| sources | Unchanged. | Unchanged. | Unchanged. |

The temporary on-disk TDB2 integration test verifies rejection persistence over
a dataset reopen, absence of an asserted write on rejection, and rejection of a
conflicting terminal decision after confirmation. It also verifies inferred and
asserted named-graph isolation.

## Image and Configuration Evidence

- The Semantic Core image has development, test, build, and non-root runtime
  stages using Java 21.
- Compose defines Fuseki/TDB2, an idempotent ontology bootstrap, the runtime
  service, and a `semantic-core-system-test` service.
- [run_system_tests.ps1](../../../scripts/run_system_tests.ps1) creates a
  unique Compose project, runs the test service after healthy Fuseki bootstrap,
  and removes containers, network, and temporary volume in `finally`.
- Development-only port exposure is in `compose.dev.yaml`; production uses an
  immutable-image contract, restart, logging, and resource limits in
  `compose.prod.yaml`.

## Exact Validation Results

| Check | Command | Result |
|---|---|---|
| Ontology regression | `docker compose --profile tools run --build --rm ontology-test` | Passed: 73/73 checks. |
| Isolated system suite | `.\scripts\run_system_tests.ps1` | Passed: 24 tests, including live Fuseki confirmation, requested-candidate SHACL validation, a valid candidate alongside an invalid one, `404 CANDIDATE_NOT_FOUND`, structured `422 application/problem+json`, restart replay, two-client concurrent terminal decisions, and transaction-derived HTTP `200` replay; temporary volume removed. |
| Compose rendering | `docker compose config`; base + dev; base + prod with `SEMANTIC_CORE_IMAGE` | Passed. |
| Runtime smoke | Build runtime target, run with `FUSEKI_BASE_URL`, request `/health/live` | Passed: HTTP 200. |
| Whitespace | `git diff --check` | Passed. |

## S3-21 Decision

Authentication remains out of Sprint 3 scope. The runtime binds project and
actor only from trusted deployment configuration and rejects client-supplied
identity fields, as the approved contract requires. The human reviewer accepted
the runtime evidence and approved M1 for Sprint 4 consumption on 2026-07-30.

## Human Approval Checklist

- [x] Accept Java 21, Javalin, Maven, Jena 6.1.0, Fuseki/TDB2, and Compose as
  the executable-foundation baseline.
- [x] Accept lifecycle graph-diff and rollback evidence.
- [x] Accept project-isolation and named-graph evidence.
- [x] Confirm the runtime evidence satisfies M1.
- [x] Approve M1.
