# Semantic Core

Semantic Core is the Java 21/Javalin service that executes Projecta's
domain-safe RDF lifecycle against Fuseki/TDB2. It accepts only the finite HTTP
operations in the [API contract](../../docs/architecture/semantic-core-api.md);
it never exposes arbitrary SPARQL or graph mutation to callers.

## Runtime flow

```text
HTTP request
  -> SemanticCoreApplication
  -> trusted project/actor context from deployment environment
  -> FusekiLifecycleService or FusekiQueryService
  -> RemoteCandidateValidationService (for validate and confirm)
  -> FusekiGateway
  -> project-scoped named graphs in Fuseki
```

For `POST /v1/candidates/{id}/validations`, the validator first verifies that
the requested candidate exists in that project's candidates graph. It builds a
small validation model from that candidate's triples, its project closure, and
the released ontology graph; then it runs the released Candidate SHACL shape.
It therefore cannot make one invalid candidate affect another candidate's
result.

For confirmation/rejection, the lifecycle service creates a fixed SPARQL
Update. Fuseki atomically changes the candidate state, writes provenance, and
persists the idempotency record. A per-attempt token stored in that record lets
the service report whether this request created the decision (`201`) or replayed
an existing one (`200`) without a pre-transaction race.

Failures are translated by `ApiErrorTranslator` at the Javalin boundary. API
errors use `application/problem+json`; candidate SHACL failures include stable,
sanitized `shape`, `path`, and `message` violations.

## Package layout

Keeping `org.projecta.semanticcore` flat is appropriate at the current size:
the roughly twenty classes form one bounded context and have short dependency
paths. Splitting now would add navigation overhead without creating a useful
ownership boundary.

Introduce subpackages only when each group has several independently evolving
classes or a separate test boundary. A natural future split is:

```text
http/         Javalin composition, requests, responses, error mapping
lifecycle/    confirmation, rejection, idempotency result types
validation/   candidate SHACL loading, results, violations
store/        FusekiGateway, graph routing, readiness
query/        allowlisted read views
```

Do not move domain records merely to fill these folders. Keep the flat package
until an actual feature makes one of those seams useful.

## Local workflow and system test

Java and Maven run inside containers; a host Java installation is not required.
From the repository root, run the isolated system suite:

```powershell
.\scripts\run_system_tests.ps1
```

The script creates a unique Compose project, starts Fuseki and the runtime,
runs the service tests, then removes its containers, network, and volume.
