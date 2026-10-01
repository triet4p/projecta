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

## [2026-08-04] Separate deterministic M4 snapshots from rebuild execution time

**Decision:** Represent each project's M4 materialization with a governed `InferenceSnapshot` marker containing the content-derived asserted `sourceRevision` and rule version. Keep rebuild execution time only in the operational response, and expose a separate content-derived `materializationRevision` for inferred and provenance graphs.
**Alternatives considered:** Infer freshness from returned rows, use triple counts and maximum timestamps as the source revision, or persist the current rebuild timestamp on deterministic derivation activities.
**Reason:** Empty result sets still need freshness semantics, count/time heuristics miss same-count mutations, and execution timestamps make identical rebuilds produce different graph content.
**Consequences:** Retrieval can detect stale or missing materializations even with zero result rows, repeated rebuilds are content-idempotent, and any future asserted blank-node support must introduce canonical RDF normalization before those nodes participate in the digest.

## [2026-08-05] Use a web-first, desktop-ready application surface

**Decision:** Use a React and TypeScript single-page web client as Projecta's canonical interaction surface, deploy it alongside the existing Compose backend, and reserve Tauri for a future thin desktop companion that calls the same Application API rather than packaging the backend topology into a desktop installer.
**Alternatives considered:** Make a self-contained Tauri desktop application the primary product and bundle Python, Java/Jena, Fuseki, and storage with it; use Electron as the primary client; use .NET MAUI or WinUI; or remain web-only without preserving a reusable desktop path.
**Reason:** Projecta's production connectors, webhook and polling flows, retries, shared semantic state, and tenant/project boundaries require an always-on server independently of any user's workstation. A React web client gives the shortest path to exercising the released M2-M4 capabilities through the existing API and Compose topology, while a static SPA can later be reused inside Tauri for native capture conveniences without creating a second semantic runtime or deployment model.
**Consequences:** Sprint 7 adds a containerized React/TypeScript web experience and keeps FastAPI, Semantic Core, and RDF storage server-owned. The client must use typed Application API contracts and never access Fuseki directly. Desktop packaging, native keyring integration, offline semantic storage, and bundled backend sidecars are deferred until an explicit native or offline requirement justifies a new decision.

## [2026-08-05] Separate interactive LLM profiles from deployment bootstrap configuration

**Decision:** Allow an authorized user-facing settings workflow to manage live LLM provider type, base URL, model, and credential through provider-neutral runtime configuration and secret-store ports, while retaining the `PROJECTA_LLM_*` environment contract as the headless, CI, and deployment-bootstrap provider rather than the only configuration source.
**Alternatives considered:** Keep all live LLM settings exclusively in `.env`; expose environment-file editing through the UI; store provider keys in browser storage; or require a desktop OS keyring before a web experience can configure the model.
**Reason:** Sprint 7 must let a user exercise extraction without editing developer files, but Projecta's server-owned workflows and future background connector jobs cannot depend on a workstation keyring or a running desktop client. Separating configuration metadata from secret material preserves fail-closed startup and deterministic CI while allowing interactive configuration without exposing credentials to the browser or committing them to Git.
**Consequences:** The application must resolve LLM configuration through an explicit abstraction, return only redacted credential status to clients, and keep raw keys out of API responses, browser persistence, logs, telemetry, and RDF. The current environment provider remains supported for tests and headless deployments; the concrete local/self-hosted secret-store adapter requires a reviewed Sprint 7 security decision, and production connector credentials still require a server-side secret manager.

## [2026-08-05] Approve the Sprint 7 web and configuration trust boundary

**Decision:** Approve the React/TypeScript static SPA as the canonical Sprint 7 client, require server-owned fixed or allowlisted local project/actor context behind a same-origin Application API boundary, and require interactive LLM settings to use provider-neutral runtime-configuration and secret-store ports while keeping raw credentials out of the browser and preserving the `PROJECTA_LLM_*` headless adapter.
**Alternatives considered:** Allow browser-selected trusted headers, expose the context secret to the SPA, make Tauri the primary runtime, keep interactive settings in `.env`, store credentials in browser storage, or allow direct browser access to Semantic Core/Fuseki.
**Reason:** The approved S7-07 boundary must let a local user exercise released M2–M4 behavior without creating client-controlled project routing, a second desktop semantic runtime, or a credential leak. Server-owned context and redacted provider configuration preserve the existing project isolation, Compose topology, deterministic headless tests, and future production authorization seam.
**Consequences:** S7-08 onward must expose only typed Application API contracts, inject context outside browser control, disable the local adapter outside the explicit experience profile, resolve LLM configuration through an operation-time snapshot, and retain the environment adapter for CI/bootstrap. Secret-store selection remains a separate S7-14 decision; this approval does not authorize a persistence backend, authentication provider, or production secret manager.

## [2026-08-05] Use application-encrypted operational storage for Sprint 7 secrets

**Decision:** Select application-encrypted operational storage as the local/self-hosted Sprint 7 secret-store baseline, accessed through a provider-neutral `SecretStore` port and opaque secret references. Keep a Vault-compatible service as the future production-shaped migration target and exclude the host OS keyring from the canonical web/Compose adapter.
**Alternatives considered:** Adopt a Vault-compatible service in the Sprint 7 Compose slice, use a host OS keyring, or defer secret-store selection until after persistence implementation.
**Reason:** Application-encrypted storage has the shortest path through the current server-owned Compose topology and supports dynamic settings writes without adding a stateful service or workstation-specific dependency. The provider-neutral port preserves a later migration path while keeping the browser boundary unchanged.
**Consequences:** S7-15 and S7-16 may implement only the approved local baseline after defining master-key custody, bootstrap, backup/recovery, rotation, concurrency, and bounded plaintext lifetime. The deployment-owned master key must never be stored in the application datastore, browser, Git, or RDF. No Vault service or OS-specific keyring dependency is part of the canonical Sprint 7 topology.

## [2026-08-10] Keep graph and knowledge navigation finite and opaque

**Decision:** Expose project graph, knowledge, and candidate workflows only through bounded typed projections with revision-bound opaque handles; never expose RDF identifiers, graph names, SPARQL, or arbitrary path traversal to the browser.
**Alternatives considered:** Let the browser navigate raw resource IDs through existing lifecycle routes, expose a general-purpose graph/RDF browser, or maintain separate unbounded graph and knowledge read models.
**Reason:** Project isolation, truthful stale-state handling, and an accessible UI require one finite server-authorized projection that preserves labels and independent lifecycle/provenance/evidence states without turning storage identifiers into browser capabilities.
**Consequences:** New graph and ID-free knowledge routes must validate allowlisted types, relations, limits, revisions, and project scope; the UI must retain handles only as internal selection state and use the same projection for the visual graph and companion table. Reversing this boundary requires explicit architecture/security approval.

## [2026-08-10] Approve structured Note source semantics without new vocabulary

**Decision:** Implement structured Note drafts by reusing released `Note`, `NoteItem`, controlled item types, project/author, evidence, provenance, candidate lifecycle, and temporal terms; keep durable item order, assignment/requester, deadline/effective date, generic status, and Note revision out of the ontology.
**Alternatives considered:** Add `itemOrder`, `assignedTo`, `deadline`/`dueAt`, generic Note status, or revision terms immediately; store the composer draft as an untyped raw Note; or defer the structured Note implementation entirely.
**Reason:** The approved competency questions establish that the current product needs auditable source evidence and projections, while the deferred concepts lack independently committed identity, lifecycle, temporal, project, and provenance semantics. Evidence offsets already provide deterministic textual order without claiming editorial order.
**Consequences:** Application workflow fields such as `draftStatus` and `sourceMetadata` remain operational and cannot be promoted to RDF facts. Semantic writes must load and validate the released ontology/shapes at the named-graph boundary, preserve raw/segment backward compatibility, and fail closed on invalid project, author, time, evidence, or provenance data. Future semantic additions require a new human-reviewed proposal and migration path.

## [2026-08-10] Route DeepSeek V4 through its documented Chat Completions contract

**Decision:** Route `deepseek-*` models through DeepSeek's documented OpenAI-compatible Chat Completions endpoint with JSON mode and thinking explicitly disabled; retain Responses JSON Schema output only for providers that implement that contract.
**Alternatives considered:** Continue using DeepSeek's undocumented `/responses` compatibility behavior, leave thinking enabled and only raise timeouts, or use DeepSeek beta strict tool calls as the extraction transport.
**Reason:** A raw production-profile probe proved that `/responses` ignored `thinking.type=disabled`, spending 2,316 reasoning tokens for 61 final tokens, while DeepSeek's V4 documentation defines the thinking toggle and JSON output on Chat Completions. The beta tool-call route would add a beta endpoint and tool semantics that extraction does not need.
**Consequences:** The provider-neutral gateway and local Pydantic validation remain unchanged, but DeepSeek structured output is JSON-valid rather than provider-enforced JSON-Schema-valid and therefore must fail closed on any schema mismatch, empty content, or token-limit truncation. SDK retries stay disabled and endpoint-specific behavior must remain isolated in the adapter.

## [2026-08-10] Publish product releases only from exact SemVer tags

**Decision:** Publish Projecta GitHub Releases only from annotated tags matching
`vA.B.C`, after all component manifests, the dated changelog section, and the
complete deterministic release gate agree with the tag version.
**Alternatives considered:** Create releases manually from `main`, accept loose
`v*` tags without validating their shape, generate notes only from commit
messages, or publish before the Compose system journey completes.
**Reason:** Projecta has independent API, web, Semantic Core, ontology, and
Compose boundaries; a branch commit alone does not prove they identify or pass
as the same product release. Changelog-authored notes also preserve the
user-facing meaning that conventional commit subjects do not capture.
**Consequences:** A release tag is immutable publication intent. The tag commit
must retain a fresh Unreleased changelog section, declare one matching product
version across component manifests, and pass API, web, Semantic Core, repository
contract, ontology, and Compose system jobs before GitHub publication.
## [2026-08-10] Run the first connector inside the Application API process

**Decision:** Run the first Sprint 10 JSON/Mock connector runtime inside the existing Application API process behind provider-neutral connector ports.
**Alternatives considered:** Extract the connector into a separate deployable runtime immediately, or add an unimplemented service scaffold before the connector kernel exists.
**Reason:** The approved vertical slice already has a server-owned FastAPI boundary and Compose topology; in-process execution keeps the first implementation reviewable and avoids duplicating authorization, project context, and typed API seams while still isolating provider behavior and state behind ports.
**Consequences:** Connector code must remain provider-neutral and bounded, while PostgreSQL operational state and evidence storage remain explicit external boundaries. Extracting the runtime later requires preserving these ports and a new deployment/operational decision; this approval does not authorize production authentication, real external connectors, or ontology changes.

## [2026-08-11] Reuse released semantics for the Sprint 10 connector

**Decision:** Treat the G1-approved Sprint 10 JSON/Mock connector as source/evidence ingestion that reuses released Note, NoteItem, candidate, lifecycle, project-isolation, and PROV-O semantics without adding ontology vocabulary.
**Alternatives considered:** Add connector, external-resource, external-identity, cursor, retry, or dead-letter terms now; keep imported content as opaque application JSON; or bypass the existing candidate review lifecycle with direct assertions.
**Reason:** The approved competency questions are answered by the released source/evidence/provenance lifecycle, while installation, event, cursor, retry, and dead-letter concepts are operational state owned by PostgreSQL and the evidence boundary. New vocabulary would commit durable domain meaning without a required semantic question and direct assertion would violate the human-review boundary.
**Consequences:** Sprint 10 may release without an ontology version change, connector operational state must remain outside RDF, actor hints cannot merge identities automatically, and any future graph-queryable external resource or connector identity requires a new governed proposal and explicit human approval.

## [2026-08-12] Approve Sprint 11 trust boundary with revisions

**Decision:** Approve Sprint 11 G1 with revisions: use Keycloak `26.7.0` in production mode with an official digest-pinned image and an isolated database/user inside the existing PostgreSQL boundary; use OpenBao `2.6.1` with digest pinning, single-node integrated Raft, internal TLS, Shamir 3-share/2-threshold manual unseal, short-lived AppRole workload authentication, and private management surfaces; use certificate-based app-only Teams access with `ChannelMessage.Read.Group` resource-specific consent for exactly one tenant/team/channel per installation; keep Projecta as the authority for sessions, memberships, exact project/installation authorization, and invalidate all Projecta sessions after cold restore; approve `NO_ONTOLOGY_CHANGE_REQUIRED`.
**Alternatives considered:** Approve the original proposals without revisions; use Entra-backed Projecta login; keep the local experience context for production; use the application-encrypted store, Compose secrets, SOPS plus `age`, or Azure Key Vault as the runtime secret manager; use delegated Teams login, refresh tokens, or the broader `ChannelMessage.Read.All` permission; attempt to restore browser sessions after cold recovery; add Teams-specific ontology vocabulary.
**Reason:** The revised baseline preserves the no-subscription and Compose-first constraints while making the trust boundaries explicit. OIDC protocol endpoints needed for login/discovery/JWKS are distinct from Keycloak administration, health, and metrics, which remain private. OpenBao provides a service-level custody boundary, but Projecta must retain exact project/installation authorization because per-installation OpenBao policy would add unnecessary Sprint 11 complexity unless separately implemented and tested. Certificate-based app-only access avoids browser/provider session coupling, resource-specific consent keeps Teams scope narrow, and session invalidation after restore avoids trusting potentially inconsistent browser authority. The existing released source/evidence/candidate/provenance lifecycle answers the Teams competency questions without new ontology terms.
**Consequences:** S11-15 onward must use the approved image tags and record immutable digests, enforce the revised public/private edge split, use one existing PostgreSQL service with isolated Keycloak ownership, measure 2 GiB/2 CPU for Keycloak and 512 MiB/0.5 CPU for OpenBao with at least 20% full-stack memory headroom, and preserve the bounded Teams limits of 100 events, 10 MiB/run, 1 MiB/event, 30 seconds, `$top=50`, 10 replies/root, and 50 replies total. Membership roles are additive and seeded by an idempotent operator CLI/file workflow without admin UI. Cold restore requires OpenBao unseal, workload re-authentication, and Projecta user login again. The accepted single-instance/manual-unseal trade-off is early-production only; no HA or unattended restart claim is allowed. Reversing these choices requires explicit new human instruction and a new decision.

## [2026-08-13] Resolve the fixed OIDC issuer through the TLS edge

**Decision:** The API resolves `https://auth.example.com/realms/projecta`
through the shared TLS edge on the service network; it must not bypass the
public protocol surface by calling Keycloak directly on port 8443.
**Alternatives considered:** Give Keycloak the `auth.example.com` network alias,
use a separate internal issuer URL, or weaken startup readiness until the edge
becomes available.
**Reason:** OIDC validates one exact issuer and Sprint 11 explicitly separates
public discovery/JWKS/login endpoints from private Keycloak management. Direct
aliasing maps the issuer's implicit port 443 to Keycloak 8443 incorrectly and
creates divergent internal/public trust paths. Starting the static web image
independently lets the edge start early enough for API discovery without
weakening API readiness.
**Consequences:** The edge owns the `auth.example.com` alias and issuer CA;
Keycloak remains reachable privately for proxying but not as the API's issuer
endpoint. Production web startup cannot depend on API health, while user-facing
traffic and release acceptance still require API/web/edge health separately.

## [2026-08-13] Release v0.6.0 with GitHub Public Issues and defer live Teams

**Decision:** Replace the Sprint 11 live Teams release gate with a
credential-free, read-only GitHub Public Issues connector bound to one exact
synthetic public repository. Keep the implemented Teams adapter and its
deterministic regression coverage, but label it experimental/deferred and make
no production-ready Teams claim in v0.6.0. Preserve all approved Keycloak,
OpenBao, session, membership, authorization, recovery, evidence, and ontology
boundaries.
**Alternatives considered:** Use the currently signed-in work Microsoft tenant;
create a personal Microsoft 365 developer tenant; release only deterministic
Teams fixtures; omit a real provider from v0.6.0; or choose an authenticated
GitHub/private-repository connector immediately.
**Reason:** The work tenant is not an authorized disposable test boundary and a
free personal Microsoft sandbox is not available. Public GitHub issues and
comments can exercise a real bounded HTTP, pagination, rate-limit, hostile-input,
cursor, replay, evidence, and isolation path with fabricated data and without a
subscription, license, tenant consent, or provider credential. This is a
narrower claim than Teams and avoids converting lack of authorization into a
security exception.
**Consequences:** Sprint 11 receives a separate G1 amendment and twenty atomic
implementation/acceptance tasks. The connector must use the fixed GitHub API
origin, accept only one validated owner/repository binding, exclude pull
requests, make no writes, perform no hidden retry, preserve the existing
100-event/10-MiB/1-MiB/30-second limits, and produce only sanitized live
evidence. S11-67 remains intentionally incomplete but no longer blocks G2/G3.
Restoring Teams as a live release claim requires a new human authorization for
a disposable tenant, application, consent, channel, data handling, and teardown.
Reversing the connector choice requires explicit new instruction and a new
decision.

## [2026-08-13] Human-approved ontology reuse for GitHub Public Issues

**Decision:** Retain `NO_ONTOLOGY_CHANGE_REQUIRED` for the exact GitHub Public
Issues issue/comment import scope. Reuse the existing source, evidence,
candidate, provenance, actor-hint, and project-isolation boundaries; keep
connector installation, provider IDs, cursor, pagination, replay, and rate
state operational rather than RDF domain truth. The project owner explicitly
approved this semantic outcome on 2026-08-13.
**Alternatives considered:** Add provider-shaped `GitHubIssue`/`GitHubComment`
classes or properties; add an `ExternalResource` module; or postpone the
semantic outcome until release approval.
**Reason:** The competency questions are answered by released Projecta
boundaries, and provider-shaped ontology terms would introduce identity,
lifecycle, temporal, and migration commitments without a new domain question.
Human semantic approval is complete, while G2 product/security/release
approval remains a separate pending gate.
**Consequences:** No ontology Turtle, SHACL, rule, version, migration, or
runtime RDF artifact is added for this connector. Any future requirement for
durable external-resource identity must reopen the ontology governance flow.

## [2026-08-13] Use authenticated gh only for disposable live-acceptance operations

**Decision:** Permit the owner-authorized `gh` CLI session for creating, seeding,
editing, reading, archiving, and deleting the disposable public GitHub repository
used by Sprint 11 live acceptance, while keeping the Projecta GitHub connector
credential-free and read-only.
**Alternatives considered:** Use anonymous `api.github.com` for all operator
actions; add a provider token to the Projecta connector; or use a work tenant or
private repository for live acceptance.
**Reason:** The secondary `triet4p` account is an authorized disposable boundary
and avoids the anonymous GitHub API rate limit during test-data lifecycle and
control-plane inspection. Passing that credential into Projecta would violate the
approved connector threat boundary, so `gh` is restricted to operator-side
repository control and evidence collection; runtime import must still exercise
the fixed-host, no-token connector contract.
**Consequences:** Live-acceptance commands must verify the active `gh` account,
use synthetic data only, bind to one exact public repository, and never persist
tokens or raw provider payloads in runtime state or artifacts. The repository is
archived or deleted after evidence capture. G2 remains pending until the
authenticated operator journey and the credential-free runtime import are both
proven by regenerated, provenance-bound evidence.

## [2026-08-14] Approve Sprint 11 G2 with a narrow GitHub quota waiver

**Decision:** Approve Sprint 11 G2 for the bounded, credential-free GitHub Public Issues release slice using the passing r9 baseline live evidence and deterministic edit/replay provenance contracts, while waiving another anonymous-quota-consuming live edit/replay attempt.
**Alternatives considered:** Wait for anonymous GitHub quota reset and repeat the complete live journey; use an authenticated provider token in the Projecta runtime; or keep G2 blocked indefinitely on external free-tier capacity.
**Reason:** The r9 baseline already proves real credential-free import, pull-request exclusion, exact candidate/evidence continuity, replay, and project isolation, while the final validator and regression contracts cover edit/replay digests, cursor chains, timestamps, snapshots, tamper rejection, and safe quota failure. Spending more anonymous quota would add limited release confidence and using a runtime token would violate the approved connector boundary.
**Consequences:** The failed edit/replay journey remains a truthful diagnostic artifact and is not relabeled as passing. v0.6.0 may claim only bounded public read-only ingestion, not GitHub capacity, availability, continuous synchronization, private repositories, or authenticated access. Release preparation may proceed, but immutable preflight, G3 exact-commit approval, tagging, and publication remain separate pending gates.

## [2026-08-14] Prove business semantic quality before resuming capability breadth

**Decision:** Make Sprint 12 a governed business-semantic dataset and evaluation
sprint, and pause new connector, continuous-synchronization, outbound-action,
and tenant-administration breadth until its held-out business-quality gate is
reviewed.
**Alternatives considered:** Continue the open M7 breadth roadmap immediately;
tune prompts and agents against the existing Sprint 5 fixtures; or build a
larger dataset without independent annotation, leakage controls, staged gates,
and human business acceptance.
**Reason:** `v0.6.0` proves strong runtime, isolation, provenance, review,
recovery, and release boundaries, but the current semantic-quality benchmark
has only eight synthetic sentence-level cases and primarily demonstrates
contract conformance. Tenant teams need evidence that realistic Quick Notes and
longitudinal project situations become correct, useful, reviewable, and
traceable knowledge with acceptable correction effort, latency, and cost.
**Consequences:** Sprint 12 must pass business-scope, dataset-contract,
annotation-pilot, dataset-freeze, baseline, optimization-freeze, blinded
held-out, and closure gates. Prompt, agent, context, model, or tool optimization
may use only the permitted development/validation splits; held-out material
remains under human custody until the candidate is frozen. Ontology gaps must
enter the governed ontology workflow rather than be force-fit. M7 remains open
but its additional breadth is deferred until Sprint 12 evidence determines the
next highest-value work.

## [2026-08-14] Approve Sprint 12 G0 business scope

**Decision:** Approve the Sprint 12 G0 business scope and authorize dataset-contract design for the eight ranked journeys, sixteen competency questions, bounded claims, independent annotation, privacy/provenance controls, and held-out custody model.
**Alternatives considered:** Reject the packet, revise the journey/claim boundary before G1, or resume connector and outbound-action breadth before business-quality evidence exists.
**Reason:** The approved scope directly measures the released v0.6.0 value chain from Quick Note through review, graph and grounded retrieval while preserving the project's human-control and isolation boundaries. It also makes the strongest future claim conditional on a named, leakage-resistant benchmark rather than implying tenant or production generalization.
**Consequences:** S12-10 is complete and G1 dataset-contract work may begin. The eight journeys, bounded non-claims, qualified annotation requirement, privacy/provenance rules, and held-out custody are now the baseline for future Sprint 12 work; changing them requires another explicit human scope decision. This approval does not approve a dataset, ontology change, model, optimization result, release, or tenant-readiness claim.

## [2026-08-14] Approve Sprint 12 G1 dataset contract

**Decision:** Approve the Sprint 12 G1 dataset contract, including the versioned atomic/scenario schemas, coverage quotas, independent annotation and adjudication rules, provenance/privacy/leakage/custody controls, metric definitions, pre-registered thresholds, and the no-change ontology reuse outcome.
**Alternatives considered:** Reject the contract, revise the quotas or scoring boundary before G2, introduce benchmark-specific RDF vocabulary, or begin scaled authoring without the custody and leakage controls.
**Reason:** The approved contract makes the G0 business questions executable against the released Projecta semantic lifecycle while keeping dataset operations outside domain truth. It freezes the measurement and safety boundary before authoring and preserves human authority over both benchmark data and ontology meaning.
**Consequences:** S12-28 is complete and G2 annotation-pilot work may begin. The schemas, quotas, guide, governance rules, metric formulas, thresholds and no-change semantic outcome are the baseline for Sprint 12; changing them requires a new version or explicit gate decision. This approval does not approve the dataset contents, model optimization, held-out access or a product release.

## [2026-08-14] Use owner-delegated AI review for the synthetic Sprint 12 track

**Decision:** Accept owner-delegated AI semantic annotation and adjudication for the repository-visible synthetic Sprint 12 pilot and development/validation corpus, while recording every artifact as non-human evidence and limiting all resulting claims to the named synthetic benchmark.
**Alternatives considered:** Require the project owner to manually annotate the corpus; leave the generated gold unaudited; misidentify agent output as human evidence; or abandon Sprint 12 evaluation work entirely.
**Reason:** The project owner cannot allocate time to manual annotation and explicitly delegated semantic review responsibility to the implementation agent. The existing generated corpus also assigned types and relations mechanically rather than from sentence meaning, so an explicit AI-review track with corrected provenance, semantic validation and digest-bound adjudication is more truthful than retaining nominal human requirements around unaudited fixtures.
**Consequences:** Agent-authored cases use `agent-authored-synthetic`, human-authored fraction is zero, and AI review may close the synthetic-track annotation tasks but can never establish inter-human agreement, qualified-human reliability, tenant generalization, target-role utility or production readiness. Test custody, runtime-backed baseline, frozen candidate and held-out business gates remain independent blockers. Reintroducing a human-evidence claim requires genuinely independent qualified annotators and a new evidence-bound approval.

## [2026-08-14] Open development optimization after accounted baseline, not baseline quality

**Decision:** Treat a runtime-backed, fully accounted baseline as sufficient to open development-only experiments, while requiring each candidate to pass schema validity and hard invariants before validation, freeze or held-out evaluation.
**Alternatives considered:** Keep the previous rule that a baseline must pass every hard invariant before any optimization; rerun or alter the historical `v0.6.0` baseline until it passes; or unlock validation and held-out work together with development experiments.
**Reason:** The Sprint 12 baseline is valid evidence that `v0.6.0` has quality failures, but requiring it to pass before optimization creates a deadlock and hides whether a candidate fixes the failure. The historical baseline must remain immutable, while candidate safety and contract validity remain strict before any promotion.
**Consequences:** G5 may register and run development experiments against the locked baseline, but candidate selection, validation, freeze, custody and G6 remain closed until a candidate has complete accounting, zero schema/normalization failures and passing hard invariants.

## [2026-08-16] Close S12-f-07 as rejected and open S12-f-08 after measurement correction

**Decision:** Treat S12-f-07 as a completed rejected experiment whose 96 executions and aggregate remain immutable, and require all corrected measurement and composed-prompt work to enter a new preregistered S12-f-08 rather than rerunning f-07.
**Alternatives considered:** Fix the runner and rerun f-07; overwrite the aggregate with corrected metrics; or continue to Stage B using the uncorrected aggregate.
**Reason:** The candidate independently regressed on missing outputs, supersession abstention, hallucination and corrected entity/relation metrics, while the aggregate also contained a field-mapping defect and provisional relation measurement. Separating closure from correction preserves both the observed model behavior and an auditable measurement erratum.
**Consequences:** S12-f-07 cannot be rerun or selected; Registry/G5 v8 records its rejection and opens S12-f-08. S12-f-08 must use canonical relation endpoints, positive-relation gates, supersession false-positive zero, composed prompt v5, and pricing bound before execution.

## [2026-08-16] Freeze S12-f-08 with evaluator v2 and cache-aware pricing

**Decision:** Require S12-f-08 to use evaluator v2, a standalone digest-guarded runner, and a bound three-class DeepSeek pricing contract before provider execution.
**Alternatives considered:** Keep evaluator v1 and bind only a prompt; reuse the closed f07 runner; or estimate cost from aggregate input/output tokens.
**Reason:** Canonical relation endpoints, positive-relation fail-closed metrics and cache-aware cost accounting materially change the measurement and execution contracts. A standalone runner makes the six-call temporal schedule, no-retry policy and evidence custody auditable.
**Consequences:** The execution package is frozen at commit `84e589bce954d8e23ad734eeb01b0711140dd854`; Registry/G5 v9 and authorization v2 bind its evaluator, runner, prompt, runtime, pricing artifact and dataset digests. Stage A remains a one-time provider operation; no Stage B or selection is authorized.

## [2026-08-16] Reject S12-f-08 after one guarded Stage A

**Decision:** Close S12-f-08 as `COMPLETED_REJECTED` after its authorized single Stage A run; do not retry, overwrite evidence, open Stage B or select a candidate.
**Evidence:** All 96/96 case-runs completed with zero hard-gate failures and zero supersession false positives, but candidate positive-relation macro F1 was `0.0476`, micro F1 `0.0488`, relation macro delta was negative, and sensitivity relation delta was negative.
**Consequences:** Registry/G5 v10 bind the aggregate and six report digests. Prompt-only optimization is not promoted; any next experiment requires a new hypothesis and preregistration against the v2 measurement contract.

## [2026-08-16] Open remediation before the next S12 Stage A

**Decision:** Keep S12-f-09 closed as rejected and open an offline remediation track before any new Stage A, candidate selection, validation, or G6 activity.
**Alternatives considered:** Rerun f09 with repaired accounting; proceed directly to S12-78 or G6; or open another provider experiment with the existing independent-arm and unversioned-slice contracts.
**Reason:** f09 evidence is complete and correctly rejects the candidate, but independent provider calls do not identify the tool effect, slice thresholds were not versioned before execution, trigger behavior was not exercised, and the authorization commit did not contain the full execution package.
**Consequences:** RM-01 through RM-05 must pass offline before a new preregistration and authorization can be issued. f09 evidence, Registry/G5 v11, validation/held-out custody, S12-78–81, S12-R24 and G6 remain unchanged and blocked.

## [2026-08-16] Preserve m3.v2 and version the trigger envelope

**Decision:** Keep the released m3.v2 extraction contract unchanged and carry the required `triggerQuote` through a new versioned relation-evidence envelope for the next tool experiment.
**Alternatives considered:** Add an optional field directly to m3.v2, rerun f09 after changing the historical contract, or leave trigger context optional for the next candidate.
**Reason:** Adding a field to m3.v2 changes the historical f08 execution-package digest without improving the already-closed f09 evidence. The next tool experiment needs an explicit trigger contract while prior experiment artifacts remain immutable.
**Consequences:** The next preregistration must bind the new envelope/schema, materializer, scorer, and tests together. f08/f09 history remains unchanged; no provider execution is authorized by this decision.

## [2026-08-21] Resolve Sprint 12 state through explicit transitions

**Decision:** Use a current-state index and later explicit decision or transition records to determine current Sprint 12 governance state, while preserving preparation and gate artifacts as immutable historical snapshots.
**Alternatives considered:** Rewrite issued v7 preparation artifacts in place; infer current state from the newest filename; or allow every gate packet and README to act as an equal source of truth.
**Reason:** RM-23F legitimately issued an exact lineage after the v7 artifacts were frozen with `NOT_ISSUED` preparation fields. Rewriting those fields would break their recorded digests and custody, while leaving precedence implicit causes documents and agents to report contradictory authorization states.
**Consequences:** Current-state consumers must follow `evaluation/sprint-12/current-state.v1.json`, the latest explicit transition, and the current gate packet in that order. Historical packet statuses remain valid only for their decision time. A transition never broadens authority beyond its explicit fields; provider execution, validation, held-out access, Stage B and promotion still require separate authorization.

## [2026-08-21] Authorize one exact S12-f-12 development Stage A execution

**Decision:** Authorize exactly one 144-call S12-f-12 development Stage A execution against commit `e047911e`, the frozen v7 package and technical freeze, report-v6 output path, no-retry/no-overwrite policy, and `$10.00` ceiling.
**Alternatives considered:** Withhold authorization after RM-24; broaden authorization to retries or Stage B; or authorize a mutable current-HEAD execution package instead of the exact frozen lineage.
**Reason:** Independent RM-25 review found the RM-24 digests, exact-commit blobs, runtime, schemas, output custody and cost boundary consistent, and the targeted regression suite passed after the preparation artifact was distinguished from a provider authorization without changing frozen evidence.
**Consequences:** The exact authorization is single-use and permits at most 144 provider calls and 96 relation-branch outputs. Validation, held-out access, Stage B, candidate selection and promotion remain closed, and authorization establishes no quality improvement or tenant-readiness claim.

## [2026-08-21] Close S12-f-12 rejected and open offline remediation preparation only

**Decision:** Close S12-f-12 as `COMPLETED_REJECTED_NO_STAGE_B` and permit only offline preparation of a superseding schema/evidence remediation.
**Alternatives considered:** Open Stage B despite failed gates; reuse the spent RM-25 authorization; close Sprint 12 without diagnosis; or authorize an immediate rerun against the existing v7 lineage.
**Reason:** The immutable Stage A report is complete and schema-valid as evidence, but the candidate produced six schema-invalid responses, 17 invalid-evidence findings and failed registered threshold and slice gates. The passing gold-relations control does not waive candidate hard failures, while sanitized evidence is insufficient to attribute sole causality to one provider, prompt or runtime component.
**Consequences:** The v6 report and RM-25 authorization remain immutable and non-reusable. Provider execution, validation, held-out access, Stage B, selection, freeze and promotion stay closed. Any future run requires offline remediation, a superseding governed lineage, exact-commit review and new owner authorization.

## [2026-08-22] Approve S12-f-12 offline diagnostic remediation implementation only

**Decision:** Approve the RM-28 finite schema/evidence diagnostic contract for offline implementation and deterministic mock testing only.
**Alternatives considered:** Reject the package because sanitized evidence cannot reveal exact malformed fields; authorize immediate superseding-lineage preparation; reuse the existing report contract without finite reasons; or infer provider/prompt causality from aggregate failures.
**Reason:** RM-28 truthfully localizes the six schema failures and 17 unsupported-evidence findings while preserving unknown validation paths and causality. Finite sanitized reason codes and reconciliation tests improve the next evidence boundary without exposing raw payloads or pretending the rejected candidate passed.
**Consequences:** Offline code and mock tests may be implemented, but superseding-lineage preparation, preregistration, freeze, provider execution, validation, held-out access, Stage B, selection and promotion remain closed pending another owner review.

## [2026-08-22] Approve superseding S12-f-12 lineage preparation only

**Decision:** Approve the corrected RM-30 finite diagnostic implementation and
authorize offline preparation of a new versioned S12-f-12 preregistration,
execution package and technical freeze, without issuing any of them.
**Alternatives considered:** Reject RM-30 after its initial audit findings;
authorize an immediate rerun; reuse or mutate the closed v7 lineage; or issue a
new preregistration and freeze in the same review.
**Reason:** The initial owner audit found two fail-closed gaps: malformed runtime
diagnostic inputs could raise, and the report schema admitted unregistered
reason codes. Both were corrected with regression coverage; the safe suite now
passes 70 tests, the finite allowlists are closed, all historical unknowns
remain explicit, and the immutable report still binds 144 calls with zero
retry. This is sufficient to prepare reviewable execution custody, but not to
issue or execute it.
**Consequences:** RM-32 may prepare a new exact-commit lineage offline and must
bind the corrected diagnostic contracts. Preregistration issuance, technical
freeze issuance, provider execution, validation, held-out access, Stage B,
candidate selection and promotion remain closed behind separate owner gates.

## [2026-08-22] Issue the superseding S12-f-12 v8 lineage without execution authority

**Decision:** Issue the exact RM-32 v8 preregistration and technical freeze
after independent RM-33 review, while withholding provider authorization and
all downstream access.
**Alternatives considered:** Issue the first RM-32 preparation despite audit
findings; keep the corrected lineage unissued; authorize execution in the same
decision; or reuse the spent v7 authorization.
**Reason:** Three audit findings were resolved before issuance: the live runner
now records finite diagnostics with exact reconciliation, the report schema
closes nested raw-data boundaries including dynamic-map keys, and the freeze
binds 22 exact git blobs at execution commit `005a35e3`. Independent fuzzing of
3,654 object nodes and 384 dynamic-map nodes rejected all registered raw-data
aliases, while zero-call preflight and mocked custody proved the 144-call,
96-branch, one-persist, no-retry and no-overwrite boundaries.
**Consequences:** RM-34 may prepare a separate exact v8 authorization. No
provider call is authorized until a later independent owner decision; the v6
report, closed v7 lineage, validation and held-out custody, Stage B, selection
and promotion remain unchanged.

## [2026-08-22] Authorize one exact S12-f-12 v8 development Stage A execution

**Decision:** Authorize exactly one 144-call S12-f-12 v8 development Stage A
execution against execution commit `005a35e3`, the issued RM-32 v8 package and
freeze, report-v8 output, no-retry/no-overwrite policy and `$10.00` ceiling.
**Alternatives considered:** Withhold authorization after RM-34; authorize a
mutable working-tree lineage; reuse the spent RM-25 authorization; or broaden
authority to retries, Stage B or downstream data.
**Reason:** Independent RM-35 review verified 22 exact runtime Git blobs, the
RM-33 custody erratum and canonical report-schema digest, self-bound zero-call
preflight, closed authorization/report schemas, and mocked custody of 144 calls,
96 branches, one persist, zero retries and rejected overwrite. The v8 output is
absent and all prior audit findings are resolved.
**Consequences:** The exact v8 runner may execute once and the authorization is
spent when execution starts. Validation, held-out access, Stage B, candidate
selection and promotion remain closed; execution establishes no quality or
tenant-readiness claim until the immutable result receives a separate owner
decision.

## [2026-08-22] Close the failed S12-f-12 v8 invocation without a retry

**Decision:** Close the single RM-36 v8 invocation as failed before report
persistence and permit only offline preparation of a runtime reconciliation
diagnosis and remediation.
**Alternatives considered:** Reuse the remaining 141-call numerical allowance;
retry the first case; infer a quality result from three responses; authorize an
immediate new lineage; or abandon diagnosis without preserving the failure.
**Reason:** The exact runner failed closed after three provider responses when
evidence reason counts did not reconcile with the first predicted-entities arm.
No report, complete accounting, aggregate cost or branch aggregate was
persisted. The single-use authorization was consumed by invocation, regardless
of unused call capacity, and therefore cannot permit a fourth call or rerun.
**Consequences:** The three calls remain partial execution facts and establish
no candidate-quality result. Offline code diagnosis and deterministic mocks may
proceed, but every future provider attempt requires corrected evidence, a new
exact lineage, issuance review and owner authorization; all downstream gates
remain closed.

## [2026-08-22] Approve offline implementation of the RM-36 reconciliation fix

**Decision:** Approve RM-38's finite reconciliation remediation for offline
runtime implementation and deterministic regression testing only.
**Alternatives considered:** Reject the diagnosis because the hidden provider
payload was not retained; diagnose every predicted relation against the
exact-pair total; remove the reconciliation guard; or immediately prepare and
authorize another execution lineage.
**Reason:** The deterministic reproducer proves that scoring counts invalid
evidence only for semantic exact pairs while diagnostics scanned every
predicted relation, allowing extra or non-exact relations to inflate reason
counts. It also proves an entity-span adapter passed three-tuples to a two-tuple
classifier. Aligning both paths to the same exact-pair domain and projecting
endpoint spans preserves the fail-closed invariant without inventing the hidden
RM-36 payload.
**Consequences:** RM-40 may implement the fix and regressions in a new offline
runtime version. The frozen v8 lineage, spent authorization and execution fact
remain immutable; superseding-lineage preparation, provider execution and all
downstream gates require later owner decisions.

## [2026-08-22] Approve preparation of a corrected post-v8 runtime lineage

**Decision:** Approve the independently reviewed RM-40 remediation and permit
offline preparation of a new exact-commit runtime lineage only.
**Alternatives considered:** Keep the remediation as a standalone diagnostic;
mutate or reuse the failed v8 lineage; issue a new freeze immediately; or
authorize another provider execution in the same decision.
**Reason:** Independent parity probes confirm the RM-40 path uses the same
greedy exact semantic-pair domain as scoring across duplicates, order, ties,
wrong predicates, reversed direction and extra or missing relations. Evidence
reasons reconcile exactly with unsupported plus missing, endpoint spans are
projected correctly, malformed detail fails closed and zero raw data is emitted.
**Consequences:** RM-42 may integrate the behavior into a new guarded runtime
and prepare preregistration/package/freeze artifacts offline. Issuance,
provider execution, validation, held-out access, Stage B, selection and
promotion remain behind later owner gates.

## [2026-08-22] Issue the corrected S12-f-12 v9 lineage without execution authority

**Decision:** Issue the exact RM-42 v9 preregistration and technical freeze
after independent RM-43 review, while withholding provider authorization and
all downstream access.
**Alternatives considered:** Issue the initial v9 preparation despite broken
default artifact paths; retain the corrected lineage as preparation only;
authorize execution in the same gate; or revive the spent v8 lineage.
**Reason:** The corrected runner loads the actual RM-42 package,
preregistration and freeze by default, its compatibility adapter returns the
exact frozen runtime bindings, 19 Git blobs match execution commit `f81103b`,
and default-path mocks prove unauthorized zero calls plus bounded 144-call,
96-branch, one-persist, no-retry and no-overwrite behavior.
**Consequences:** A separate task may prepare an exact v9 authorization. No
provider call is authorized until another independent owner decision; v6
custody, failed v8 evidence and all downstream gates remain unchanged.

## [2026-08-22] Authorize one exact S12-f-12 v9 development Stage A execution

**Decision:** Authorize exactly one 144-call S12-f-12 v9 development Stage A
execution against execution commit `f81103b`, the issued RM-42 v9 package and
freeze, report-v9 output, no-retry/no-overwrite policy and `$10.00` ceiling.
**Alternatives considered:** Withhold authorization after RM-44; authorize a
mutable working-tree lineage; reuse the spent RM-35 authorization; or broaden
authority to retries or downstream data.
**Reason:** Independent RM-45 review verified 19 exact runtime Git blobs, the
provider/model/prompt/dataset contract, self-bound zero-call preflight, closed
authorization/report schemas, and default-path mocked custody of 144 calls,
96 branches, one persist, zero retries and rejected overwrite. The v9 output is
absent and all RM-43 issuance bindings remain exact.
**Consequences:** The exact v9 runner may execute once and the authorization is
spent when execution starts. Validation, held-out access, Stage B, candidate
selection and promotion remain closed; a separate owner decision must review
the immutable result or failure fact.

## [2026-08-22] Reject S12-f-12 v9 and open offline error analysis only

**Decision:** Close the completed v9 Stage A as rejected with no Stage B and
permit only offline preparation of a v6/v9 error comparison and remediation
options.
**Alternatives considered:** Open Stage B despite failed hard gates; select v9
because schema-invalid responses decreased from six to five; reuse the spent
authorization; authorize immediate remediation implementation; or stop without
preserving the newly available finite diagnostics.
**Reason:** The schema-valid immutable report accounts for all 144 calls and 96
branches with zero retries, but fails hard gates with five out-of-source entity
spans and 20 invalid-evidence relations, plus registered thresholds and slices.
Invalid evidence increased from 17 in v6 to 20 in v9, so the one-response schema
improvement does not establish candidate or business-quality improvement.
**Consequences:** RM-48 may compare sanitized v6/v9 failure clusters and prepare
bounded remediation options offline. Runtime implementation, new lineage,
provider execution, validation, held-out access, Stage B, selection and
promotion remain closed pending another owner review.

## [2026-08-22] Harden diagnostics before building offline parity fixtures

**Decision:** Approve RM-48 Option A followed conditionally by Option B: first
harden finite offline diagnostics, then build deterministic scorer/materializer
parity fixtures only after all diagnostic stop criteria pass. Retain Option C,
stopping provider experimentation, as the mandatory fallback.
**Alternatives considered:** Stop immediately under Option C; authorize live
runtime remediation; build parity fixtures before closing diagnostic contracts;
or infer provider/prompt causality from v6/v9 case-run differences.
**Reason:** Independent recomputation confirms the descriptive comparison,
including three overlapping schema failures, 17 overlapping evidence failures,
clean gold-relations controls and all 15 slices. The v9 reason codes improve
observability but do not establish causality. Closed finite diagnostics and
local parity fixtures can test measurable boundaries without spending provider
calls or reconstructing withheld payloads.
**Consequences:** RM-50 may implement Option A and, only after its schema,
reconciliation, unknown and raw-data stop criteria pass, Option B. Live runtime
changes, new lineage, provider execution and downstream gates remain closed;
failure of the offline criteria returns the track to owner review under Option C.

## [2026-08-22] Stop f12 provider experimentation after RM-50 accounting gaps

**Decision:** Reject RM-50 and activate Option C, stopping further f12 provider
experimentation and runtime integration while permitting only offline closure
documentation and error-backlog preparation.
**Alternatives considered:** Continue a fourth RM-50 patch/audit loop; approve
the implementation because pristine fixtures pass; open a runtime-integration
proposal despite residual accounting gaps; or authorize another provider run.
**Reason:** Successive audits closed raw-key, cluster, case/run, arm/stage and
fixture identity gaps, but RM-50 still accepts coordinated mutations to calls,
responses, pricing, usage, cost, ceiling and hard failure-class accounting.
That violates Option A's exact-reconciliation stop criterion and allows a
valid-looking report that no longer matches immutable v6/v9 evidence. The
pre-registered fallback therefore applies.
**Consequences:** RM-52 may prepare the f12 closure packet and prioritized error
backlog. RM-50 remains rejected evidence; no more patch loop, runtime lineage,
provider execution, validation, held-out access, Stage B, selection or
promotion is authorized. Reopening requires a new owner decision and a complete
immutable accounting contract outside this closed track.

## [2026-08-22] Adopt the human-first extraction kernel for RM-55 contract work

**Decision:** Adopt the revised human-first extraction kernel as the design
contract for RM-55 and later work: immutable source-version-bound Unicode
anchors, fail-closed finite candidate lifecycles, server-owned project-scoped
handles, deterministic evidence, append-only revision-bound review receipts,
approved-only atomic assertion plans, revision-bound inference invalidation and
raw-data-excluding telemetry.
**Alternatives considered:** Accept framework v1 without policy resolution;
implement the existing extraction path incrementally without a source-version
kernel; or postpone the design until provider or held-out evaluation work.
**Reason:** RM-52/RM-53 custody is offline-only and the framework must prevent
the observed out-of-source evidence failures, stale or cross-project identity,
implicit approval, and mutable accounting/custody claims before any contract or
runtime implementation proceeds. The v2 design resolves the kernel defaults
while keeping owner-gated study decisions and ontology production changes
outside this gate.
**Consequences:** RM-55 may define the immutable SourceVersion/source-receipt
contract only. No provider reopening, auto-approval, bulk relation approval,
ontology release, held-out/validation access, Stage B, selection, promotion or
release is authorized; future ontology terms require the separate ontology
governance workflow and human approval.

## [2026-08-22] Defer RM-68 external validation during development

**Decision:** Mark Phase F-RF as `DEVELOPMENT_COMPLETE_EXTERNAL_VALIDATION_DEFERRED_DEV_ONLY` while keeping RM-68 a blocked, unchecked, non-preregistration packet until an explicit owner reopen decision verifies external custody and a frozen evaluable candidate.
**Alternatives considered:** Fabricate or infer custody readiness from repository-visible material; issue the RM-68 preregistration without a non-reconstructible payload; leave development status ambiguous; or continue provider, held-out, human-execution, selection, or promotion work.
**Reason:** RM-53 through RM-67 have sufficient development-contract, implementation, and offline-gate evidence, but the authoritative RM-68 prerequisites remain absent: no external custodian, non-reconstructible payload, frozen candidate, or human records. A finite dev-only waiver records the achieved engineering boundary without converting preparation into external or business evidence.
**Consequences:** Future agents may continue bounded development maintenance and must preserve all RM68 issuance/execution locks. Reopening RM-68 requires new owner authority plus custody receipt, non-reconstructibility, opaque dataset/configuration/evaluator bindings, and frozen candidate evidence; no provider, held-out, human, business-validation, selection, promotion, or release path is enabled by this decision.

## [2026-08-22] Supersede RM-68 defer with an internal agent-proxy PoC

**Decision:** Supersede the development-only RM-68 defer only for a bounded internal synthetic PoC: use a versioned representative dataset, the deterministic/offline default path, and explicitly non-human agent-proxy review evidence; keep RM-68 external validation, business-quality acceptance, provider execution, held-out access, and production authority closed.
**Alternatives considered:** Wait indefinitely for external custody; treat repository-visible synthetic fixtures as external evidence; call a provider to obtain candidate outputs; or let the agent-proxy results satisfy the RM-67 human-study contract.
**Reason:** The user confirmed that external custody will not be available and authorized a transparent engineering proof of concept. A synthetic, digest-bound selection and fail-closed default-path run can test protocol plumbing and accounting without fabricating human or external evidence; missing candidate output must remain a scored failure rather than being replaced by invented success.
**Consequences:** The internal PoC may produce diagnostic dataset, proxy-review, and correction-burden artifacts labeled `INTERNAL_DEV_POC_ONLY`. It cannot issue RM-68, satisfy independent reviewer agreement or manual-baseline requirements, claim business quality, or enable provider/held-out/human/production paths. The prior defer entry remains immutable historical context; any external or business evaluation still requires a distinct owner decision and real custody evidence.

## [2026-08-22] Accept the internal source-only agent-proxy PoC boundary

**Decision:** Replace the development defer path with a versioned internal source-only agent-candidate and primary-agent-proxy correction-burden PoC, accepting F-RF only as `F_RF_POC_COMPLETE_AGENT_PROXY_ACCEPTED` while keeping external human, business-quality, provider, held-out, and production claims closed.
**Alternatives considered:** Keep the prior internal PoC failure as the terminal development result; treat the synthetic records as external human evidence; or reopen external custody and human-study execution.
**Reason:** The owner supplied a frozen v5 candidate and explicit primary-agent judgments showing 60 source-supported finalized-for-review assertions, zero unsupported assertions, 12/12 unchanged items, and zero provider calls; this is sufficient to establish the bounded engineering PoC without fabricating independent human evidence or custody.
**Consequences:** RM-68 may be accepted only for the internal PoC scope and must retain the historical blocked non-preregistration packet. Any later external study or business claim requires new owner authority and fresh custody/evaluable-candidate evidence; timing, independent agreement, and human-study thresholds remain unclaimed.

## [2026-08-22] Narrow F-RF PoC acceptance after dense-hard v1 failure

**Decision:** Retain the v5 internal source-only agent-proxy result only as a
bounded baseline under `F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V1_FAILED_REMEDIATION_REQUIRED`.
The dense-hard v1 evaluation is authoritative diagnostic evidence: its frozen
candidate fails the edit-burden gate. The v5 result must not be generalized to
a “good enough,” low-correction, or broad extraction-quality claim.

**Alternatives considered:** Tune or rerun the frozen v1 candidate; merge the
dense-hard failure into the v5 score; reopen provider or human validation; or
discard the v5 baseline entirely.

**Reason:** The immutable dense-hard v1 recomputation reports 0/24 unchanged,
0/24 minor, 8 major, 2 reject, and 14 abstain items; 74 semantic edits (mean
3.0833333333), entity F1 0.5685279188, relation F1 0.1758241758, and 74/138
unsupported finalized assertions. These results are incompatible with the
RM-67 edit-burden thresholds even though the earlier v5 proxy packet remains a
valid bounded engineering baseline.

**Consequences:** S12-DH-01 through S12-DH-03 are complete for v1 evidence;
remediation is pending new authority and must be evaluated on fresh dense-hard
v2 cases with no source/gold/candidate reuse. Provider, human, external,
held-out, production, selection, promotion, and release claims remain closed.

## [2026-08-23] Authorize bounded dense-hard remediation and fresh v2 benchmark

**Decision:** Authorize DH-04/DH-05 to implement a generic offline source-only
candidate protocol and guard, and to author one fresh synthetic dense-hard v2
benchmark packet. This authority covers protocol and benchmark artifacts only;
it does not authorize a v2 candidate, scoring, review, provider call, or state
transition.
**Alternatives considered:** Tune or reuse the frozen v1 packet; expose v1 gold
or case content through a remediation fixture; create a candidate before the
guard contract is independently checked; or reopen human, provider, external,
held-out, production, selection, promotion, or release work.
**Reason:** The v1 failure identifies finite remediation classes requiring a
generic occurrence/anchor, type, relation-grounding, abstention, and quarantine
contract. A fresh packet is needed to test the contract without leaking or
reusing v1 source, gold, IDs, digests, or sentences.
**Consequences:** The v2 protocol and benchmark remain synthetic,
non-production, source-only, and offline. This author is ineligible to produce
or judge a v2 candidate because the private gold and manifest are visible here.
Any v2 candidate/evaluation requires new authority, fresh bindings, and an
independent evaluator; all provider, human, external, held-out, production,
selection, promotion, and release claims remain closed.

## [2026-08-23] Authorize DH-09/DH-10 fresh dense-hard v3 protocol and benchmark

**Decision:** Authorize bounded offline DH-09/DH-10 work to publish a corrected
source-only v3 protocol/evaluator contract and author one fresh synthetic
dense-hard v3 benchmark. The authority covers protocol, schemas, source, gold,
manifest, validator, and no-reuse lineage artifacts only; it does not authorize
a candidate, evaluation, provider call, review, or state transition.
**Alternatives considered:** Reuse or patch v1/v2 cases; score type without a
public semantic rubric; allow type uncertainty to cascade into relation or
abstention metrics; or reopen provider, human, external, held-out, production,
selection, promotion, or release work.
**Reason:** The v2.1 audit identified missing public type semantics and evidence
boundary ambiguity. A fresh v3 packet must publish finite type decision rules,
occurrence-independent typing, punctuation-normalized evidence identity,
explicit abstention/quarantine rules, and RM-67 definitions before any future
candidate can be considered.
**Consequences:** v3 remains synthetic, non-production, source-only, and
offline. No v1/v2 IDs, raw text, normalized sentences, source digests, or
artifacts may be reused. Any v3 candidate/evaluation requires new authority and
an independent evaluator; provider, human, external, held-out, production,
selection, promotion, and release claims remain closed.

## [2026-08-24] Authorize fresh dense-hard v4 offline source-only packet

**Decision:** Authorize DH-12/DH-13 to publish an immutable v3.1 stratified
adjudication of the frozen v3 diagnostic and a fresh synthetic dense-hard v4
source-only protocol, evaluator contract, and 32-case benchmark packet. The
authority is limited to offline schemas, validators, tests, digests, lineage,
and documentation; it does not authorize a v4 candidate, evaluation, review,
provider call, human/external/held-out run, state transition, selection,
promotion, or release claim.
**Alternatives considered:** Pool correction and safety cases under one
denominator; reuse or patch v1-v3 cases; create a v4 candidate or evaluation;
or reopen provider, human, external, held-out, production, selection,
promotion, or release work.
**Reason:** The v3 diagnostic exposed a denominator design failure rather than
unsafe behavior. A stratified adjudication makes that historical result
interpretable, while a fresh 24-utility/8-safety packet tests the revised
source-only contract without leaking prior IDs, text, sentences, or digests.
**Consequences:** v3.1 remains a non-authoritative offline adjudication of the
frozen v3 candidate, and pooled v3 remains diagnostic only. v4 is synthetic,
non-production, source-only, and candidate-free; the author is ineligible to
produce or judge a v4 candidate. All provider, human, external, held-out,
production, selection, promotion, and release claims remain closed.

## [2026-08-24] Close dense-hard v4 failure and require strategy redesign

**Decision:** Accept the immutable dense-hard v4 evaluation as authoritative
offline diagnostic evidence for the bounded internal track and set the current
status to `F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED`.
Retain the v5 easy internal agent-proxy result only as historical baseline
evidence; retain v1, v2, v3, v3.1, and v4 diagnostics and their measurement
corrections without pooling or generalized low-correction claims. Authorize
only the finite offline remediation/strategy-redesign backlog in
`docs/sprint-plans/sprint-12/dense-hard-v4-remediation-backlog.v1.md`.

**Alternatives considered:** Treat v4 as a passing safety result because
abstention mode precision/recall passed; average v4 with v3.1 or the v5 easy
baseline; tune or rerun the frozen candidate; authorize v5, provider, human,
external, held-out, production, selection, promotion, or release work; or
silently weaken the stratified gates.

**Reason:** The immutable v4 candidate fails the utility correction gate
(unchanged 0.0416666667, unchanged-or-minor 0.0416666667, mean edits 3.625,
26 unsupported finalized assertions) and the safety gate (8 unsafe finalized
assertions and quarantine recall 0.5), despite exact full/partial abstention
mode rates. The residuals require strategy redesign across occurrence coverage,
relation grounding, proposition-level quarantine, and utility/safety routing;
the evidence does not justify a low-correction or generalized quality claim.

**Consequences:** The v4 evaluation and remediation backlog are offline,
synthetic, and non-production. No v5 candidate, provider call, human study,
external custody, held-out inspection, production enablement, selection,
promotion, release, or generalized quality claim is authorized. The v5 easy
baseline remains historical only; any future candidate requires a new owner
decision, a fresh packet/strategy, independent evaluation, and explicit safety
and correction gates.

## [2026-08-31] Make evidence-first assisted authoring the active product direction

**Decision:** Supersede AI-first full-document extraction as the active product
direction with human-authored structured capture and bounded, optional,
on-demand local AI suggestions, while preserving candidate/asserted/inferred
separation and all historical Sprint 12 evidence.
**Alternatives considered:** Continue dense-hard extraction remediation as the
primary product path; stop AI assistance entirely; or keep whole-document
candidate extraction as the default and add stronger review gates afterward.
**Reason:** Dense-hard v4 shows that whole-document extraction creates too much
correction and unsafe finalization risk, while the accepted RM-55--RM-67
contracts already support source-versioned anchors, confirmed identities,
deterministic evidence, append-only receipts, approved-only materialization,
and adversarial guards. Starting from a human task/question or structured note
keeps the user in control, permits a zero-model path, and makes retrieval and
one bounded suggestion useful without paying for unnecessary document-wide
calls.
**Consequences:** Sprint 13 must deliver human-authored entity capture first,
then optional local suggestions and controlled relations. AI may propose only
bounded local items after scoped evidence and human selection; it may not create
global IDs or offsets, auto-approve, bulk-materialize, call providers in the
background, or become authoritative. Retrieval is context only. Per-user and
per-project budgets, caching/deduplication, and cost-per-accepted-assertion
telemetry are required. Sprint 12 dense-hard v1--v4 and the v5 easy baseline
remain immutable historical diagnostics; RM-68 external/human/business/provider
and held-out claims stay closed, and R6/R7 require a separate owner decision.

## [2026-09-28] Keep optional suggestions on an explicit loopback Ollama path

**Decision:** Route user-requested Sprint 13 item/type/link suggestions through
the Ollama generate API at `127.0.0.1:11434` only, with no proxy inheritance,
redirects, retries, startup health calls, or model downloads. Select the model
only through `PROJECTA_LOCAL_SUGGESTION_MODEL`; leave it disabled when that
setting is empty and unconditionally disabled in production. Persist workflow
state, proposal output, idempotency, and UTC daily budget counters in the
existing private operational SQLite database, while binding human decisions to
the existing append-only review receipt service.

**Alternatives considered:** Reuse the configurable LLM profile/provider path,
allow a caller-supplied model endpoint, start or download a local runtime from
the API, or keep suggestion and budget state only in process memory.

**Reason:** The active contract authorizes optional local inference but no
provider execution. A fixed loopback destination with `trust_env=False` makes
the privacy boundary independent of external profile settings, and an explicit
model setting avoids implicit inference. SQLite provides transactional
deduplication and shared budget checks across API requests without adding a
second storage convention.

**Consequences:** Operators must run Ollama separately inside the API process's
network namespace and configure a model before local suggestions are available.
The API never starts Ollama or pulls a model. Production exposes no suggestion
generation or decision capability, and a suggestion decision does not write a
graph assertion.

## [2026-09-28] Accept S13-05 telemetry denominators and date classification

**Decision:** The owner chose “Accept current §5 metrics” for S13-05. A mean
local-attempt cost is null when no cost-known accepted assertions exist.
Review-latency samples require a recorded workflow start and durable receipt
time; without a recorded start, the sample is excluded rather than imputed. A
manual date field contributes to edit counts but adds no RM-65 dimension: a
date-only edit has no correction category, while composite edits are classified
from their recognized dimensions using RM-67 major-over-minor precedence.

**Alternatives considered:** Treat an empty accepted-assertion denominator as
zero; impute missing review starts; exclude every edit containing a date from
category counts; classify date-only edits as `unchanged`; or add date as an
RM-65 dimension.

**Reason:** This records the owner's acceptance of the existing denominator and
latency behavior and clarifies the per-field date exclusion. It prevents an
unclassified date from masking a category supplied by recognized dimensions in
a composite edit. These metrics remain descriptive product telemetry, not
RM-67 study results.

**Consequences:** Contract §5 documents this decision as provenance. Null means,
missing-start latency exclusion, date-only category omission, and composite
RM-67 precedence remain the accepted behavior. No provider, human study, or
RM-68 evaluation is authorized.

## [2026-09-29] Bootstrap local Compose secrets outside the template

**Decision:** Keep `.env.example` free of reusable secrets, make its non-secret
defaults runnable in the local experience profile, and generate unique connector,
context, and Fernet credentials into the Git-ignored `.env` with one idempotent
PowerShell bootstrap command before Compose startup.
**Alternatives considered:** Commit fixed demo credentials so copying the
template alone starts Docker, or require operators to maintain the previous
multi-step inline setup recipe.
**Reason:** The owner chose a short local bootstrap rather than public reusable
secrets. The application-encrypted store requires a deployment-owned Fernet key,
and embedding it or a trusted-context secret in a tracked template would break
the existing secret-custody decision while making an exposed local server unsafe.
**Consequences:** Local startup is copy, bootstrap, then Compose; bootstrap
preserves existing non-placeholder credentials, refuses production-mode files,
and never prints secrets. Production remains separately configured and cannot
inherit this experience template as a deployment credential source.

## [2026-09-30] Carry Core-issued candidate handles in capture results

**Decision:** Include the canonical project-scoped opaque review handle beside
the capture candidate ID in each exact-span capture response.
**Alternatives considered:** Have the browser derive a handle from the Core ID,
match by label or queue order, or add a second lookup call after capture.
**Reason:** The candidate queue owns the opaque handle used by every review
route. Semantic Core can issue that exact handle from the trusted project and
captured candidate identity using the same projection algorithm, preserving
project scope without heuristic matching or an extra round trip.
**Consequences:** Capture consumers navigate with the returned handle while
retaining the Core ID only as capture identity; the API schema and fixtures must
keep both identities distinct.

## [2026-09-30] Use Core route-compatible handles in Project Overview

**Decision:** Derive Overview `node-h-`, `note-h-`, and `candidate-h-` handles
with the shared opaque-ID helper over each exact project-scoped resource.
**Alternatives considered:** Keep generic `item-h-` identifiers and teach Core
to accept aliases, derive handles in the browser from labels/order, or duplicate
the hashing implementation in ProjectWorkspaceQueryService.
**Reason:** A live Recent Note click reached Core with `item-h-…` and failed
route validation (HTTP 400). Core already owns the destination route families;
sharing its derivation preserves project isolation and prevents drift without
heuristic matching or relaxed route validation.
**Consequences:** Overview producers must preserve typed route prefixes and the
exact project-scoped resource identity; consumers continue to treat handles as
opaque and cannot infer them from display labels.

## [2026-09-30] Select the Windows 11 x64 per-user launcher for local installation

**Decision:** Select the Windows 11 x64 per-user Projecta launcher with bundled native API, Semantic Core, Fuseki/TDB2, and PostgreSQL services, serving the existing SPA from a loopback origin for one local OS user, with no Docker, WSL2, administrator installation, or user-installed runtimes; preserve the Compose developer/CI baseline.
**Alternatives considered:** The proposal's managed Podman/WSL2 route using OCI services and a hosted browser service.
**Reason:** The owner explicitly selected “Windows 11 x64 launcher” and requested continuation after the proposal compared the routes; this provides the requested no-Docker user path while retaining the existing Compose developer/CI workflow and service/API contracts.
**Consequences:** This approves installation architecture only, not exact binaries/signatures/redistribution terms, platform or resource minimums, production, any release, or `1.0.0`. Exact runtime selection/licensing, DPAPI-backed secret handling, non-destructive Fuseki bootstrap, lifecycle/backup/recovery, platform/resource measurements, and clean no-Docker verification remain S14-08 implementation/evidence requirements. Do not automatically migrate Compose data; keep the developer/CI Compose configuration unchanged.

## [2026-09-30] Provision the approved first-run native workspace instead of blocking startup

**Decision:** The native launcher provisions the proposal-§4 first-run workspace (selected display name, generated valid project ID, fixed local actor) on fresh data directories only, passing it through the existing bootstrap/catalog contracts; the FIRST_RUN_PROJECT_SETUP_NOT_AUTHORIZED blocker is removed.
**Alternatives considered:** Keep blocking start pending a new owner authorization, or add a separate project-management/create-project operation.
**Reason:** Proposal §4 already authorizes first-run-only provisioning ("A first-run wizard writes an app-owned configuration file ... It seeds only a fresh data directory"); blocking on it re-litigates a settled approval. A new create-project operation would exceed the launcher's scope.
**Consequences:** Start succeeds on fresh installs with a real catalog project; provisioning never overwrites existing config; S14-09–11 portable-data contract remains the only path for cross-machine state.

## [2026-09-30] Resolve staged API imports with an explicit sys.path bootstrap for embeddable Python

**Decision:** Launcher child commands for the CPython embeddable distribution insert the staged api/src via sys.path plus runpy.run_module instead of relying on PYTHONPATH, cwd, or mutating the install tree.
**Alternatives considered:** Rewrite python312._pth at startup, write a .pth file into the install tree, or copy the API into site-packages.
**Reason:** The embeddable interpreter ignores PYTHONPATH and cwd (verified: sys.path contains only the ._pth entries); install-tree mutation breaks read-only/signature goals and the site-packages copy breaks migrate.py parents[3] alembic resolution.
**Consequences:** Bundled python -c bootstrap commands are the contract for API children; file-executed scripts (bootstrap_fuseki.py) are unaffected as they use stdlib only.

## [2026-09-30] Verify native updates with detached Ed25519 signatures

**Decision:** Sign the exact bytes of the root `runtime-manifest.json` with a detached base64 Ed25519 signature, embed the owner-approved raw public key in the frozen launcher, and verify the complete SHA-256/size inventory before installing an update.
**Alternatives considered:** Trust a hash-only manifest, rely on an online update service, or make Authenticode certificate signing the only package-integrity mechanism.
**Reason:** The per-user runtime must verify updates offline and fail closed without an owner trust anchor; `cryptography` is already a locked API dependency, and Ed25519 gives the launcher an explicit offline trust root without depending on a certificate-store lookup or network service.
**Consequences:** The private release key stays outside the repository and user data; release builds require the owner's verified public key and a signature over the final manifest. Host-validation packages remain `releaseEligible: false`, unsigned, and non-distributable, and update application is disabled when the trust anchor is missing.

## [2026-09-30] Keep native validation unsigned and gate release signing on owner identities

**Decision:** The default native package build remains unsigned and non-distributable. An explicit release build requires an externally stored owner Ed25519 private key, its matching public trust anchor, a current code-signing certificate from `CurrentUser\My`, and an HTTPS RFC 3161 timestamp endpoint; it Authenticode-signs and verifies all packaged PE images and signs the final runtime manifest with detached Ed25519.
**Alternatives considered:** Embed signing material in the repository or package, publish a hash-only manifest, use Authenticode as the only offline update trust mechanism, or allow unsigned validation output to look release-eligible.
**Reason:** A per-user offline update needs a pinned public trust root and whole-package inventory, while Windows executable provenance needs Authenticode. Keeping private keys external and release eligibility opt-in makes host-validation evidence distinct from owner-authorized distribution.
**Consequences:** Release signing fails before package output when any identity is absent or invalid; the normal package never inherits an owner trust key merely because an environment variable is present. Signing and legal redistribution approval do not establish clean-host, owner-trial, or release-readiness approval.
## [2026-10-01] Use the second Windows workstation for native iteration

**Decision:** Use the owner's second Windows workstation directly for local native-app iteration and testing instead of provisioning or running a virtual machine.
**Alternatives considered:** Continue the current-worker VM route or use the current development workstation for dependency debugging.
**Reason:** The owner wants practical dependency issues repaired quickly and wants to avoid VM setup complexity; the second machine already has VS Code, npm, and Python. Those tools also mean a run there is developer-host validation, not clean-install or clean-dependency proof.
**Consequences:** The second machine is for manual local use only; this decision does not authorize VM provisioning or treat it as a remote server. Manual installation/start guidance must be provided and followed locally, and remains unverified. Retain the signed/clean acceptance gate. The requested 0.7.0 handoff is not approval to publish this unsigned, non-distributable variant; explicit signing-policy approval for the exact artifact remains pending. No code/package version change, tag, or release is authorized by this decision.

## [2026-10-01] Record authorized 0.7.0 publication without waiving the signing gate

**Decision:** Publication of Projecta 0.7.0 as downloadable single easy-start installers is explicitly owner-authorized, while publication of the current unsigned host-validation package remains blocked.
**Alternatives considered:** Treat the 0.7.0 request as only a handoff with no publication authorization, or interpret it as permission to publish the unsigned variant and waive the retained signed-install gate.
**Reason:** The owner explicitly authorized publication of the 0.7.0 downloadables but did not authorize an unsigned variant or waive the signed-install gate; the prior wording that described the request as no publication approval was overbroad.
**Consequences:** Do not ask the owner to re-authorize this same 0.7.0 publication. Publish only after owner-held Authenticode/Ed25519/timestamp configuration produces the exact signed installers, or after an explicit unsigned 0.7.0 exception; this does not establish clean-install proof, complete S14-08, or authorize `1.0.0`.

## [2026-10-01] Permit the owner-authorized unsigned 0.7.0 test pre-release

**Decision:** Apply an explicit unsigned pre-release exception only to the Projecta 0.7.0 Windows 11 x64 easy-start installer; keep ordinary release signing and signed-update verification fail-closed.

**Alternatives considered:** Retain the signed-installer-only requirement for this exact test asset, or broaden an unsigned exception to other versions or artifacts.

**Reason:** The owner explicitly authorized an unsigned 0.7.0 pre-release for second-machine testing and a downloadable 0.7.0 handoff, so renewed approval is unnecessary. This narrow exception does not require a fake signature or weakening the signed update trust boundary.

**Consequences:** Only the 0.7.0 test pre-release may use this exception. Do not set `releaseEligible`, bypass signature checks, or infer clean S14/1.0.0 acceptance. The exception does not grant third-party redistribution rights: before distribution, the owner must confirm the five app-local Microsoft Visual C++ DLLs meet the applicable Visual Studio license and REDIST-list terms.
