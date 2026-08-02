## [2026-07-27] Use Docker Compose as the deployment baseline

**Decision:** Use OCI containers and Docker Compose as the shared local, CI, and early-production baseline; deploy early production on a single Linux VM and introduce Kubernetes only when concrete availability or scaling requirements justify it.
**Alternatives considered:** Installing infrastructure dependencies directly on developer machines, using local and production Kubernetes from the start, and using containers only for local development while deploying production applications by a separate process.
**Reason:** Projecta has a polyglot and stateful stack—Python, TypeScript, Java/Jena, PostgreSQL, and Fuseki/TDB2—so containers reduce setup cost and version drift, while Compose keeps local development free and operationally simpler than Kubernetes. Reusing the same immutable application images and service contracts in production preserves meaningful parity without forcing developers to reproduce production infrastructure topology.
**Consequences:** Every deployable service needs a multi-stage Dockerfile, Compose configuration becomes a first-class artifact, CI must build and test the production images, and TDB2 must remain single-owner with tested backup/restore procedures. Kubernetes manifests are deferred and must not replace Compose as the default developer workflow without an explicit new decision.

## [2026-07-27] Evolve ontology incrementally with agent drafts and human approval

**Decision:** Use the `projecta-evolve-ontology` skill for competency-question-driven ontology proposals and local draft implementations, while reserving semantic approval, release, and production migration authority for a human reviewer.
**Alternatives considered:** Designing the ontology comprehensively upfront, allowing agents to modify production semantics autonomously, and limiting agents to analysis without creating reviewable ontology artifacts.
**Reason:** Projecta's domain model is too broad to design correctly upfront or by one developer alone, but ontology terms affect validation, inference, migrations, permissions, and long-lived meaning. Agent-generated vertical changes provide useful breadth and implementation leverage while an explicit human review gate preserves domain accountability and prevents suggestions from becoming production truth.
**Consequences:** Every ontology change must start from competency questions, include impact and validation artifacts, and remain marked pending review until explicitly approved. Agents may edit version-controlled drafts but may not publish ontology releases, mutate runtime datasets, or claim human approval.

## [2026-07-27] Keep Projecta skills repository-local

**Decision:** Store Projecta-specific skills only under `.agents/skills` and do not maintain a duplicate installation under the user's global Codex skills directory.
**Alternatives considered:** Keeping the canonical source under a root `skills` directory, installing only under the global Codex directory, and maintaining synchronized repository and global copies.
**Reason:** Ontology governance skills must evolve atomically with Projecta's initialization documents, ontology artifacts, and decision records. A repository-local single source prevents stale global behavior from silently applying obsolete semantic rules to this project.
**Consequences:** Agents working on Projecta must discover and use `.agents/skills/projecta-evolve-ontology`; changes must be made there and versioned with the repository. Any future global installation requires a new explicit decision and a synchronization strategy.

## [2026-07-28] Adopt w3id.org/projecta base IRI and naming conventions

**Decision:** Use `https://w3id.org/projecta/ontology/` as the base IRI with `projecta:` as the single vocabulary prefix for Sprint 1; PascalCase for classes, camelCase for object and datatype properties, kebab-case for named individuals, and `<ClassName>Shape` for SHACL shapes. Version IRI follows `https://w3id.org/projecta/ontology/v/{MAJOR}.{MINOR}/`; instance data lives under `https://w3id.org/projecta/data/` with project-scoped sub-paths.
**Alternatives considered:** purl.org (equally viable but w3id.org has stronger W3C community governance); hypothetical domains like projecta.dev (no domain ownership); module-specific prefixes like `comm:` and `core:` from the start (premature modularization for the kernel phase); retaining the `brse:` placeholder prefix from earlier documentation examples (role-specific, not product-oriented).
**Reason:** A stable, persistent base IRI that does not depend on domain ownership is essential for an ontology-driven platform whose contracts span connectors, services, and data. W3C Permanent Identifier Community Group hosting achieves that without operational overhead. A single flat namespace keeps the Sprint 1 kernel simple — authoring and querying 10–15 terms across separate module namespaces adds complexity with no benefit until the term count grows. camelCase for properties aligns with community practice (Dublin Core, FOAF, Schema.org) and reads naturally in SPARQL.
**Consequences:** All Turtle/TriG files, SHACL shapes, SPARQL queries, and named graph IRIs must use the approved namespace. The `brse:` prefix used in illustrative examples within docs/initialization/ is superseded and must not appear in new artifacts. Module sub-namespaces (core, comm, work, etc.) are authorized only after Sprint 1 when the kernel reaches a term count that justifies modularization. w3id.org registration must be completed before the first public release.

## [2026-07-28] Run Jena CLI via docker compose, not host install or raw docker run

**Decision:** Build a custom `projecta-jena:6.1.0` image from `docker/jena/Dockerfile` and run all Jena CLI tools (`riot`, `sparql`, `tdb2.tdbloader`, `shacl`) via `docker compose run --rm jena <command>`. The image includes Python 3 + rdflib so SPARQL query testing handles TriG named graphs natively. Test runner scripts live in `scripts/`, not `ontology/`.
**Alternatives considered:** Installing Jena binaries directly on the host (rejected — pollutes host, creates version drift); using prebuilt `stain/jena` image (rejected — doesn't include Python/rdflib, version not pinned, last updated 2024); raw `docker run` with volume mounts (rejected — `docker compose run` provides consistent project-level configuration).
**Reason:** Docker Compose is the deployment baseline per the [2026-07-27] decision. A custom image pins Jena to 6.1.0 (latest stable, May 2026), includes rdflib for TriG named-graph support without workaround files, and keeps all configuration in `docker-compose.yml`. Scripts in `scripts/` keep operational tooling separate from ontology source artifacts.
**Consequences:** Any CI pipeline or developer running tests must use `docker compose run --rm jena`. The image must be rebuilt when Jena or its dependencies change. No temp/demo Turtle files should be created to work around TriG limitations — rdflib handles named graphs natively inside the container. The `scripts/test-runner.sh` is the single entry point for all ontology validation.

## [2026-07-28] Use the canonical repository layout for semantic tooling

**Decision:** Keep `compose.yaml` as the single base Compose topology, place the Jena/Fuseki image under `infra/docker/fuseki`, keep executable validation tools under `scripts`, store ontology governance documents under `docs/ontology`, and colocate Sprint 1 review artifacts under `docs/sprint-plans/sprint-1`.
**Alternatives considered:** Retaining a parallel `docker-compose.yml`, keeping a root-level `docker` directory, leaving validation code under `ontology/competency-questions`, and retaining a root-level `artifacts` directory.
**Reason:** The approved repository and deployment designs already define root Compose overlays, infrastructure under `infra`, executable tooling under `scripts`, and durable documentation under `docs`. A second layout created competing entry points and made it unclear which files were canonical.
**Consequences:** This supersedes only the path and Compose-file details of the earlier Jena CLI decision; Jena 6.1.0, the custom image, Docker-based execution, rdflib TriG handling, and `scripts/test-runner.sh` remain unchanged. Commands must use `docker compose -f compose.yaml`, and new work must not introduce parallel Compose manifests or new top-level infrastructure/artifact directories without an explicit decision.

## [2026-07-28] Use a Docker-native ontology validation entry point

**Decision:** Run the complete ontology suite through the Compose service
`ontology-test` using
`docker compose run --build --rm ontology-test`. The service invokes
`scripts/validate_ontology.py` inside the pinned Jena image; the Python runner
calls Jena `riot` for RDF syntax and rdflib for deterministic query assertions.
**Alternatives considered:** Keeping the host-side Bash wrapper, adding a
PowerShell wrapper alongside it, and documenting a sequence of raw
`docker compose run jena` commands.
**Reason:** A Compose service is one cross-platform entry point for Windows,
Linux, and CI. It keeps Jena and Python dependencies inside the container and
avoids requiring Bash, WSL, or duplicated host scripts.
**Consequences:** This supersedes the `scripts/test-runner.sh` entry-point
details in the earlier Jena CLI and canonical-layout decisions. Ontology
validation must remain runnable with the single Compose command above, and the
service must exit nonzero when any syntax, vocabulary, competency-query, or
negative-fixture assertion fails.

## [2026-07-28] Release ontology v0.1 with kebab-case controlled IRIs

**Decision:** Approve the repository-local Projecta ontology v0.1 release, use
kebab-case IRIs for all nine `NoteItemType` controlled individuals, license the
ontology under Apache 2.0, and defer w3id.org registration until before the
first public release.
**Alternatives considered:** Retaining PascalCase controlled-individual IRIs,
using a data-specific license such as CC-BY-4.0, and registering the public
w3id.org redirect during Sprint 1.
**Reason:** Kebab-case follows the already approved namespace decision and
avoids collisions with future PascalCase domain classes such as
`projecta:Requirement`. Apache 2.0 keeps repository and ontology licensing
consistent. Registration is unnecessary for a repository-local baseline but
remains mandatory before public IRI publication.
**Consequences:** The released controlled IRIs are
`projecta:requirement`, `projecta:decision`, `projecta:question`,
`projecta:task`, `projecta:risk`, `projecta:assumption`,
`projecta:constraint`, `projecta:progress-update`, and
`projecta:research-need`. Future releases must not reuse or silently rename
them; incompatible changes require deprecation and migration guidance.

## [2026-07-28] Use RDF reification (rdf:Statement) for v0.2 assertion metadata

**Decision:** Use standard RDF reification (`rdf:Statement` with `rdf:subject`, `rdf:predicate`, `rdf:object`) to attach provenance and temporal metadata to individual assertions in the v0.2 ontology. The v0.2 vocabulary adds Projecta-specific metadata properties (`validFrom`, `validTo`, `ontologyVersion`, `prov:wasAssociatedWith`, `prov:endedAtTime`) on `rdf:Statement` instances.

**Alternatives considered:** Assertion Node (custom `projecta:Assertion` class with `hasAssertion` indirection — breaks all v0.1 direct-property queries and requires data migration) and RDF-star (`<< s p o >>` quoted triples — no native SHACL target support, SPARQL-star is not a W3C Recommendation, Protégé/JSON-LD/OWL do not support it).

**Reason:** The S2-05 benchmark evaluated all three representations on query complexity, SHACL compatibility, update safety, and v0.1 backward compatibility. RDF reification scores highest (weighted 24 vs 22 for assertion node vs 19 for RDF-star) because: (1) it preserves v0.1 direct-property queries unchanged — all 32 Sprint 1 checks continue to pass; (2) it supports native SHACL shapes via `sh:targetClass rdf:Statement`, which S2-11 through S2-14 require; (3) it is supported by every RDF tool since the 1999 specification. The duplication risk (value in both direct triple and `rdf:object`) is mitigated by a SHACL consistency shape that detects drift.

**Consequences:** All v0.2 assertion metadata (review decisions, temporal validity intervals, supersession links) use `rdf:Statement` instances in the provenance graph alongside direct triples in the asserted graph. SHACL shapes in S2-11–S2-14 target `rdf:Statement` for metadata validation and target domain classes directly for base fact validation. RDF-star is deferred for re-evaluation in Sprint 3+ (when W3C standardization and SHACL quoted-triple support may be available). Assertion node representation is deferred for consideration in a hypothetical v1.0 release when breaking query-surface changes are permitted.

## [2026-07-29] Use Java 21, Javalin, and Maven for Semantic Core

**Decision:** Implement the Sprint 3 Semantic Core with Java 21, Javalin 7.x, Maven, Apache Jena 6.1.0, and a JVM runtime container image.
**Alternatives considered:** Kotlin on the JVM, Spring Boot, and Quarkus (including a native-image delivery path).
**Reason:** The Semantic Core is a small, internal, transaction-heavy Jena/Fuseki service. Java matches Jena's primary API and Java 21 requirement without an added Kotlin compiler or native-image compatibility burden; Javalin keeps the domain-safe HTTP boundary explicit and lighter than a full application platform while retaining embedded-server lifecycle control and testability. The approved Compose-first workflow makes a JVM image sufficient until measured deployment requirements justify native compilation.
**Consequences:** Service code, dependency management, tests, and image stages use Maven and Java 21 inside containers; contributors do not need a host Java installation. Javalin-adjacent JSON, validation, logging, and test dependencies must be selected explicitly. Spring Boot and Quarkus are not introduced unless a future decision reverses this baseline, and native-image work is deferred.

## [2026-07-31] Use uv for the Python application build baseline

**Decision:** Use uv with Python 3.12, `pyproject.toml`, and committed `uv.lock` for the FastAPI application.
**Alternatives considered:** Poetry with `poetry.lock`, and maintaining separate pip requirements files alongside either project manager.
**Reason:** Both uv and Poetry provide a reproducible lock and can run pytest, Ruff, and pyright, but the repository already runs a UV-managed Python 3.12 inside the pinned Jena image. uv keeps Python selection, dependency synchronization, and command execution in one pinned container-friendly tool, avoiding an additional Poetry installation layer for the first Python vertical slice.
**Consequences:** S4-09 must create and commit one `uv.lock`; development, CI, and every API container stage use locked uv synchronization. Poetry files and parallel requirements files are not introduced, and commands in UV-managed images use `uv run` rather than assuming `python3` is on `PATH`.

## [2026-08-01] Release ontology v0.3 and the M2 Manual Quick Note slice

**Decision:** Approve Sprint 4 and release the additive ontology v0.3.0 evidence
extension together with the M2 Manual Quick Note vertical slice.
**Alternatives considered:** Keep the validated implementation as
`0.3.0-draft`, release the API while leaving its semantic contract pending, or
defer exact evidence offsets to a later slice.
**Reason:** The canonical suite passes 103 ontology checks, Java verification,
and 10 API end-to-end tests. Unicode code-point offsets, source/candidate graph
validation, project isolation, transaction rollback, idempotency, provenance,
and v0.1/v0.2 compatibility have executable evidence and passed human review.
**Consequences:** New M2 captures propose ontology version `0.3.0` and use the
strict evidence shapes. Exactly `0.1.0` and `0.2.0` retain legacy validation;
unknown or malformed versions fail closed through current strict shapes. The
release is additive and requires no existing-data backfill. Authentication,
authorization, public deployment, edit/delete, LLM extraction, and inference
remain outside the released scope.

## [2026-08-02] Use OpenAI Responses API as the first M3 provider adapter

**Decision:** Implement the first live M3 provider adapter against the OpenAI Responses API with strict structured JSON Schema output, while keeping `LLMGateway` provider-neutral and selecting the model only from required runtime configuration.
**Alternatives considered:** Google Gemini structured output, Anthropic Messages tool-schema output, and a self-hosted vLLM OpenAI-compatible endpoint.
**Reason:** The benchmark found OpenAI's structured-output contract and Python/Pydantic integration provide the smallest typed adapter surface for the current extraction slice, with explicit refusal/status and usage handling; replay remains the canonical CI path. This is a provider adapter choice, not a domain or ontology contract.
**Consequences:** S5-15 may add the pinned OpenAI SDK only behind the gateway adapter. Runtime must provide `OPENAI_API_KEY` through the deployment secret boundary and a non-empty model configuration; no credential or provider payload is stored in Git or telemetry. Replacing OpenAI later must change only adapter/configuration code and preserve the gateway, extraction schema, ontology, and API contracts. Gemini, Anthropic, and vLLM remain eligible future adapters.

## [2026-08-02] Route the first Responses adapter through DeepSeek

**Decision:** Use the OpenAI-compatible Responses API through the configurable DeepSeek endpoint for the first live M3 adapter, with `OPENAI_RESPONSE_BASE_URL`, `OPENAI_RESPONSE_API_KEY`, and `PROJECTA_LLM_MODEL` as deployment configuration.
**Alternatives considered:** Direct OpenAI-hosted Responses API from the earlier S5-08 decision, Google Gemini structured output, Anthropic tool-schema output, and replay-only execution.
**Reason:** The user explicitly selected the DeepSeek Responses API guide while retaining the OpenAI-compatible request/response abstraction. This preserves the provider-neutral gateway and lets canonical CI remain replay-based while real calls target the configured DeepSeek endpoint.
**Consequences:** The adapter must not hardcode a DeepSeek URL or model, must fail closed without the API key/model, and must normalize compatibility differences at the adapter boundary. The earlier OpenAI-hosted choice is superseded for the first live endpoint; changing endpoint/provider remains a configuration/adapter change and cannot alter the domain contract.

## [2026-08-02] Require one explicit PROJECTA_LLM environment contract

**Decision:** Require `PROJECTA_LLM_TYPE`, `PROJECTA_LLM_BASE_URL`, `PROJECTA_LLM_API_KEY`, and `PROJECTA_LLM_MODEL` for every live LLM startup and accept only `openai-response/openai` as the current type.
**Alternatives considered:** Preserve the earlier `OPENAI_RESPONSE_*` aliases, retain source defaults for the DeepSeek URL/model, or silently disable live extraction when configuration is incomplete.
**Reason:** Provider selection and credentials must be deployment-owned and auditable; source fallbacks caused the evaluator to use an unintended `/v1` endpoint instead of the user’s `.env` configuration.
**Consequences:** Missing or unsupported configuration fails closed at settings/evaluator startup. No legacy aliases, URL/model defaults, or skip/fallback path may be reintroduced; future provider types must be added as an explicit reviewed contract change.

## [2026-08-02] Accept the explicit openai-response and openai LLM types

**Decision:** Set `PROJECTA_LLM_TYPE` to either `openai-response` or `openai`; both use the current OpenAI-compatible Responses adapter while the remaining endpoint, credential, and model values come from the required `PROJECTA_LLM_*` variables.
**Alternatives considered:** Keep the erroneous combined value `openai-response/openai`, accept arbitrary provider strings, or add separate unreviewed adapter behavior for `openai`.
**Reason:** The environment contract needs a simple provider/type discriminator with two explicit values and must reject typos without reintroducing defaults or fallback routing.
**Consequences:** Settings and live evaluation validate against exactly these two values; adding another type requires an explicit contract and adapter decision.

## [2026-08-02] Approve the Sprint 5 v0.4 extraction ontology

**Decision:** Approve the additive v0.4 ontology, SHACL shapes, fixtures, and competency queries for M3 typed entity, relation, and bounded same-project link candidates.
**Alternatives considered:** Keep the artifacts as proposal-only, defer approval to a later sprint, or remove the candidate-specific vocabulary and retain opaque application JSON.
**Reason:** The user explicitly approved the Sprint 5 ontology after implementation and validation; the candidate boundary, exact evidence, provenance metadata, allowlists, and same-project constraints are sufficiently defined and tested for the M3 slice.
**Consequences:** The v0.4 vocabulary is approved for Sprint 5 and remains additive to v0.3 with no data migration. Candidates remain reviewable proposal data and are never automatically asserted; future semantic changes require a new reviewed ontology decision.

## [2026-08-02] Make v0.4 runtime validation and candidate lifecycle canonical

**Decision:** Treat the approved v0.4 M3 ontology as a runtime contract: persist candidates under the canonical project candidate route, load v0.4 SHACL shapes and ontology modules in Semantic Core, resolve only existing same-project canonical entity IRIs, and persist abstention activity provenance even when no candidate is produced.
**Alternatives considered:** Keep note-local candidate IRIs, validate only in the API, reconstruct generic `/entity/{id}` targets, or omit empty extraction provenance.
**Reason:** Those alternatives allowed lifecycle lookup mismatches, fabricated/cross-project targets, unvalidated v0.4 payloads, and unauditable abstentions; the release boundary requires the Semantic Core to enforce the approved semantic contract at its mutation boundary.
**Consequences:** Candidate confirmation/rejection/validation now operate on the same IRIs emitted by ingestion, v0.4 is included in canonical ontology regression, and every extraction outcome has durable provenance. Any future ontology version must add an explicit runtime shape/version path and regression fixture.

## [2026-08-02] Amend v0.4 with allowlist declarations and abstention provenance

**Decision:** Amend the approved v0.4 ontology to declare every M3 allowlisted entity class and relation predicate, add `Team` for bounded link context, and add `abstentionReason` as an optional extraction-activity audit property.
**Alternatives considered:** Leave runtime allowlists broader than the ontology, reuse an unrelated existing term, or keep abstention only in application telemetry.
**Reason:** Runtime SHACL must validate the same vocabulary that the API accepts, and empty extraction outcomes must be queryable from persisted provenance without relying on logs.
**Consequences:** The v0.4 approval remains valid with this additive amendment; the canonical ontology suite and runtime bootstrap must include the amended terms, and future allowlist changes require another reviewed amendment.

## [2026-08-03] Release the Sprint 5 M3 extraction slice with prompt v2 and a bounded evidence retry

**Decision:** Release the Sprint 5 M3 slice with prompt `m3.prompt.v2` (nine entity type definitions, minimal-span and code-point rules, abstention/link rules, and five few-shot examples) and a single bounded live-runner retry for the `invalid_evidence` error class only, after two consecutive passing runs of the corrected live quality gate.
**Alternatives considered:** Keep `m3.prompt.v1` and record an explicit quality acceptance decision for over-extraction; add normalization-level link filtering for relation endpoints; retry all normalization failures or relax fail-closed evidence validation.
**Reason:** The corrected live gate exposed real over-extraction, span, and abstention failures that thin guidance caused; prompt fixes and an evidence-only retry restored every threshold to `1.0` while keeping safety classes (`hallucinated_link`, cross-project) fail-closed. Accepting the old behavior or filtering at normalization would mask model quality instead of fixing it.
**Consequences:** The live quality gate now requires two consecutive passing runs because single-run model output is noisy; any prompt change must be revalidated against the full `s5.v1` dataset; the product path still fails closed on invalid evidence without retry. The evaluation runner may spend bounded extra provider calls on evidence noise.
