# Lessons Learned

Append-only log of bugs, surprises, and environment-specific workarounds.

## [2026-07-28] Use Docker for Jena CLI; do not install Jena/Fuseki on host

**Symptom:** S1-12 requires Apache Jena CLI tools (`riot`, `sparql`) to validate ontology files and run competency queries. Host-installed Java 21 is available but Jena binaries are not present.
**Root cause:** Jena/Fuseki is a Java distribution that must be downloaded and extracted. Installing it on the host pollutes the development environment and creates version drift between developer machines.
**Fix / workaround:** Build a custom `projecta-jena:6.1.0` Docker image from `docker/jena/Dockerfile` with Jena 6.1.0 + Fuseki + Python3/rdflib. Run all CLI tools via `docker compose run --rm jena <command>`. Test runner lives at `scripts/test-runner.sh`. No host installation needed beyond Docker Desktop.
**Watch out for:** Future tasks that need Jena CLI (SHACL validation in Sprint 2, TDB2 loading, rule execution). Always use `docker compose run --rm jena` rather than raw `docker run`. Do not create temp/demo workaround files — the container has both Jena and rdflib, so TriG named graphs are handled natively. Test scripts belong in `scripts/`, not `ontology/`.

## [2026-07-28] Turtle/TriG compact URIs cannot contain "/"

**Symptom:** TriG file `quick-note-demo.trig` failed to parse with `rdflib` when using compact URIs like `proj-data:project/ecommerce-checkout`.
**Root cause:** Turtle/TriG prefixed names (compact URIs, e.g., `prefix:localname`) must conform to the XML NCName production. The `/` character is not allowed in NCNames.
**Fix / workaround:** Use full IRIs (`<https://w3id.org/projecta/data/project/ecommerce-checkout>`) for instance data where the IRI template contains path segments. Use prefixed names only for flat vocabulary terms where the local name is a single identifier (e.g., `projecta:Note`).
**Watch out for:** Any Turtle/TriG file that uses path-based instance IRI templates. Either use full IRIs or define additional prefixes that avoid slashes in local names.

## [2026-07-28] rdflib Graph.parse() silently drops TriG named-graph content

**Symptom:** When parsing `quick-note-demo.trig` with `rdflib.Graph.parse()`, the triples inside the named graph block were silently ignored (data triples = 0).
**Root cause:** `rdflib.Graph` is a flat triple store with no graph context. TriG parsing routes named-graph triples to their respective contexts, which a plain `Graph` cannot hold. The parser does not error — it simply discards the triples.
**Fix / workaround:** Parse TriG with `rdflib.Dataset` (which supports named graphs), then manually merge all graph contexts into a plain `Graph`: `g = rdflib.Graph(); for ng in ds.graphs(): for t in ng: g.add(t)`.
**Watch out for:** Any rdflib code that loads TriG files. Always use `Dataset` for TriG, then merge if a plain graph is needed for SPARQL querying.

## [2026-07-28] Parallel infrastructure layouts hide the canonical entry point

**Symptom:** The repository had placeholder `compose.yaml` overlays but the working Jena topology lived in a separate `docker-compose.yml`; Docker files and sprint summaries also appeared in new root-level directories.
**Root cause:** Sprint tasks optimized their local artifact placement without reconciling it with the approved structures in `06-Tech-Stack.md` and `08-Deployment-Choice.md`.
**Fix / workaround:** Merge working services into the canonical root `compose.yaml`, keep environment-only overrides in `compose.dev.yaml`/`compose.prod.yaml`, place image sources under `infra/docker`, executable tooling under `scripts`, and sprint evidence under `docs/sprint-plans/<sprint>/`.
**Watch out for:** Before adding a top-level directory, Compose manifest, runner, or generated evidence folder, search the initialization documents and decisions for an existing canonical location. Extend that location instead of creating a parallel hierarchy.

## [2026-07-28] Match pip flags to the base image's packaged pip version

**Symptom:** The Jena tools image failed to build because pip rejected the
`--break-system-packages` option.
**Root cause:** Ubuntu 22.04 installs a pip version that predates that option.
**Fix / workaround:** Install rdflib with `pip3 install --no-cache-dir rdflib`
in the current `eclipse-temurin:21-jre-jammy` image.
**Watch out for:** When changing the base image or Python installation strategy,
verify supported pip options during the image build instead of assuming host and
container pip versions match.

## [2026-07-28] A host Bash wrapper weakens Docker workflow portability

**Symptom:** The ontology runner required Git Bash or a configured WSL
distribution on Windows even though every validation dependency already lived
inside the Docker image.
**Root cause:** Compose orchestration was wrapped in `test-runner.sh`, making the
host shell an accidental prerequisite.
**Fix / workaround:** Model the suite as the `ontology-test` Compose service and
run it with `docker compose run --build --rm ontology-test`.
**Watch out for:** Prefer container entrypoints or Compose services for
cross-platform workflows. Add host-shell wrappers only when they provide
platform-specific value and are not the sole canonical entry point.

## [2026-07-29] Jena SHACL CLI exit status does not indicate conformance

**Symptom:** The ontology suite reported passing SHACL positive fixtures even
when a Jena validation report contained violations.
**Root cause:** `shacl validate` exits with status 0 after producing a valid RDF
validation report regardless of the report's `sh:conforms` value. It also loads
TriG as a graph and warns that named-graph data is ignored.
**Fix / workaround:** Parse Jena's Turtle report and require exactly one
`sh:conforms true` for positive fixtures; require `sh:conforms false` plus the
expected result message for negative fixtures. Evaluate graph-sensitive
`sh:sparql` isolation constraints against an unflattened `rdflib.Dataset` with
TriG fixtures.
**Watch out for:** Any Jena CLI SHACL check over TriG or any test that treats a
zero exit status as data conformance. Keep graph-agnostic Jena SHACL checks
separate from named-graph dataset checks.

## [2026-07-29] UV-managed Python is not available as python3 in the Fuseki image

**Symptom:** The `fuseki-bootstrap` Compose service failed at startup with
`exec: "python3": executable file not found in $PATH` even though the shared
Fuseki/Jena image installs Python through UV.
**Root cause:** `uv python install` stores the managed interpreter under
`UV_PYTHON_INSTALL_DIR`; it does not create a system `python3` executable on
`PATH` in the Java runtime image.
**Fix / workaround:** Invoke the script through `uv run --offline python` so
UV resolves its installed managed interpreter without a network request.
**Watch out for:** Any Compose entrypoint or shell command in the Fuseki/Jena
image that assumes a system Python binary after only `uv python install`.

## [2026-08-02] Java ingestion must validate Unicode evidence against source text

**Symptom:** The initial M3 Semantic Core ingestion validation accepted evidence when offsets were ordered, even if the evidence text did not match the raw note or offsets crossed a supplementary Unicode code point.
**Root cause:** Validation checked only numeric offset bounds and did not independently verify the source substring. Java string indexing is UTF-16 based while the M3 contract uses Unicode code-point offsets.
**Fix / workaround:** Normalize line endings, convert the source to a code-point array, and require each candidate’s evidence text to equal the code-point slice before SHACL validation or persistence.
**Watch out for:** Any cross-language evidence contract involving emoji or other supplementary characters; offset validation must be repeated at every persistence boundary.

## [2026-08-02] DeepSeek Responses requires its dedicated model and root base URL

**Symptom:** Requests sent with the legacy `deepseek-chat` model and `/v1` base URL returned HTTP 400 from the Responses endpoint; after compatibility correction, some long generations exceeded the original ten-second timeout.
**Root cause:** DeepSeek’s Responses API guide currently limits the Responses surface to `deepseek-v4-flash`, documents `https://api.deepseek.com` as the base URL, and the provider can take longer than the initial low timeout for some cases.
**Fix / workaround:** Use the documented root base URL and `deepseek-v4-flash`, omit unsupported request fields, provide a fully required strict schema, and use a 60-second timeout with bounded retries for transient malformed/timeout responses.
**Watch out for:** Chat API model defaults and `/v1` compatibility settings must not be copied into the Responses-specific configuration without checking the provider’s current compatibility table.

## [2026-08-02] Approved ontology can still be absent from the runtime contract

**Symptom:** Sprint 5 documentation marked v0.4 approved while candidate ingestion emitted note-local IRIs, Semantic Core lifecycle used a different candidate route, and runtime/canonical SHACL validation excluded the approved v0.4 shapes.
**Root cause:** Semantic approval was recorded as documentation state without completing the runtime version path, canonical IRI contract, bootstrap module list, and release regression suite.
**Fix / workaround:** Emit project-scoped `/candidate/{id}` IRIs, load v0.4 ontology/shapes in bootstrap and Semantic Core, resolve canonical same-project targets at the mutation boundary, persist empty extraction provenance, and add v0.4 syntax/query/positive/negative checks to the 119-check suite.
**Watch out for:** A human-approved ontology is not release-ready until its shapes are loaded at every write boundary and its canonical IRIs, lifecycle transitions, fixtures, and regression suite agree.

## [2026-08-02] SHACL target closure must include referenced asserted entities

**Symptom:** Relation/link candidates passed API allowlists but could fail Semantic Core SHACL because the validation model contained candidate payloads without the asserted target resources.
**Root cause:** The validation boundary treated the candidate graph as self-contained even though v0.4 range and same-project constraints depend on target entity declarations in the asserted graph.
**Fix / workaround:** Add bounded relation/link target closure from the trusted asserted graph to both pre-commit and post-ingestion validation, and declare the complete runtime allowlist in v0.4.
**Watch out for:** Any SHACL `sh:class`, project-scope, or target-existence constraint that references another graph must explicitly load a trusted closure before validation.

## [2026-08-02] Containerized tests must not assume repository-relative parent depth

**Symptom:** API runtime crashed in `/app` while loading configuration, and the replay fixture test failed during collection because local `Path.parents[...]` assumptions do not exist in the container image.
**Root cause:** Local source layout and container layout differ; the runtime image receives configuration through Compose and the test image needs an explicit evaluation fixture mount.
**Fix / workaround:** Discover a local `.env` only when it exists, let Compose inject runtime variables, and mount `evaluation/` read-only with an explicit `PROJECTA_REPLAY_FIXTURE` path for system tests.
**Watch out for:** Never encode host repository depth into production startup or container test fixtures; fail clearly when an explicitly required path is absent.

## [2026-08-03] Exact-span quality gates can fail because the gold annotation is wrong

**Symptom:** A live extraction was reported as having an incorrect exact span even though its end offset matched the Unicode code-point length of the source text.
**Root cause:** The `s5.v1` gold case annotated a 44-code-point sentence with `endOffset: 45`, and the replay fixture repeated the same invalid bound. Evaluator comparisons trusted the gold payload without first validating it against the source.
**Fix / workaround:** Correct both fixtures to offset 44 and make the evaluator fail closed by validating every gold evidence slice and its bounds before computing quality metrics.
**Watch out for:** Replay agreement is not proof that gold evidence is valid. Validate gold spans independently whenever datasets, provider probes, or cross-language Unicode offsets change.

## [2026-08-03] SPARQL JSON replay parsing must not depend on serialization whitespace

**Symptom:** A repeated M3 extraction succeeded on its first request but returned `409 INVALID_LIFECYCLE_STATE` on the idempotent replay.
**Root cause:** Semantic Core extracted the note IRI by searching for the exact substring `\"value\":\"`; Fuseki emitted standards-compliant SPARQL JSON with spaces around separators, so the existing replay record appeared unavailable.
**Fix / workaround:** Parse `results.bindings[0].note.value` with Jackson, require exactly one binding, and cover pretty-printed SPARQL JSON with a regression test.
**Watch out for:** Never parse JSON or SPARQL result sets with fixed string markers; formatting and binding order are not contract guarantees.

## [2026-08-03] Canonical system tests must separate provider transport from application E2E

**Symptom:** The canonical Compose E2E could fail or be skipped based on live provider credentials and model output, making implementation regressions indistinguishable from external quality failures.
**Root cause:** The system runtime used the configured external LLM even though the Sprint 5 acceptance task required a credential-free replay path.
**Fix / workaround:** Run the canonical HTTP API/Semantic Core/Fuseki chain with the versioned `ReplayGateway` fixture, and keep the DeepSeek probe as a separate explicit live-quality gate.
**Watch out for:** External-provider evaluations may supplement deterministic E2E but must not replace it or redefine implementation pass/fail status.

## [2026-08-03] A thin extraction prompt causes live over-extraction and span drift

**Symptom:** The live quality gate failed with entities precision 0.25, links precision 0.33, exact-span 0.75, and abstention recall 0.75: the model proposed extra entities/links, emitted whole-sentence spans instead of minimal phrases, and extracted from ambiguous and cross-project notes.
**Root cause:** `m3.prompt.v1` provided classification guidance for only 3 of 9 entity types and had no rules for minimal evidence spans, punctuation, abstention on ambiguous/out-of-project content, or link-vs-relation overlap. Strict JSON schema enums cannot prevent a wrong-but-allowlisted type or extra candidates.
**Fix / workaround:** Promote to `m3.prompt.v2` with one-line definitions for all nine types, minimal-span and code-point rules (an emoji is exactly one offset), full-sentence punctuation retention, request/abstention/link rules, and five few-shot examples. A single-case probe is not a sufficient quality signal; run the full dataset gate.
**Watch out for:** Every prompt change must be validated against the full `s5.v1` dataset, not one case; label/type guidance alone cannot stop span noise.

## [2026-08-03] LLMs miscount Unicode code points even with explicit offset guidance

**Symptom:** A live gate run failed with `invalid_evidence` on the emoji case (`🚀 Le sẽ kiểm tra API thuế.`) and the link case even though the same cases passed in the immediately preceding run; the model emitted offsets that did not match the source slice.
**Root cause:** Non-deterministic model output: the model occasionally counts emoji/supplementary characters as two offsets (UTF-16 style) or emits a mention that differs from its own span text. Normalization intentionally fails closed on any evidence mismatch.
**Fix / workaround:** Add a single bounded retry in the live runner for the `invalid_evidence` error class only (`hallucinated_link` and other safety classes still fail closed), plus emoji code-point guidance in the prompt. Require two consecutive passing gate runs as evidence because single-run results are noisy.
**Watch out for:** Any live quality gate over Unicode notes will see occasional `invalid_evidence` noise; do not treat one failing run as a quality regression or relax the fail-closed normalization.

## [2026-08-03] A local .env silently turns fail-closed runner tests into live calls

**Symptom:** `test_live_runner_fails_without_required_configuration` returned 0 and reported `completed` even though the test explicitly removed all `PROJECTA_LLM_*` environment variables.
**Root cause:** `Settings` auto-discovers the repository `.env` (`_projecta_env_file()` walks parents of `config.py`), so popping process environment variables does not remove configuration when a `.env` file exists. The subprocess then ran the real provider with the real key.
**Fix / workaround:** Skip that test with `pytest.mark.skipif` when the repository `.env` exists; the fail-closed behavior is still verified in environments without a `.env`.
**Watch out for:** Any test that expects configuration to be absent must account for the discovered `.env`; running evaluation tests on a machine with a live `.env` spends real provider credits.

## [2026-08-03] Jena TDB2 keeps files locked on Windows even after dataset.close()

**Symptom:** `Tdb2LifecycleIntegrationTest` failed on the Windows host with `TempDirDeletionStrategy$DeletionException: Failed to delete temp directory` for every `Data-0001/*.bpt|.dat|.idn` and `journal.jrnl` file, even though the assertions passed. The failure did not occur in Linux containers.
**Root cause:** Jena TDB2 memory-maps its files, and on Windows the mapped handles survive `dataset.close()`; the TDB2 `StoreConnection` stays cached per location, so `close()` alone never releases the files. POSIX allows deleting open files, which is why the same tests pass in containers.
**Fix / workaround:** Open the test dataset with `DatabaseMgr.connectDatasetGraph(location, StoreParamsBuilder.create(...).fileMode(FileMode.direct).build())`, then after the final close call `StoreConnection.release(Location.create(...))` followed by `StoreConnection.internalReset()` (Jena's own test-suite cleanup). `internalReset()` must come only after the last open dataset, because it shuts down the shared transaction coordinator and breaks subsequent reopens of the same location.
**Watch out for:** Any host-side Java test that opens on-disk TDB2 with `@TempDir` on Windows. `release()` alone is insufficient — without `internalReset()` deletion still fails.

## [2026-08-03] Reused fuseki-data volume breaks the remote lifecycle integration test

**Symptom:** `FusekiRemoteLifecycleIntegrationTest.executesConfirmationAndRejectionAgainstRemoteFuseki` failed at `assertTrue(validation.conforms(project, "remote-candidate"))` with violation "A Candidate must have exactly one candidateStatus from the LifecycleStatus vocabulary" even though the test had just seeded the candidate as `validated`.
**Root cause:** The test seeds its candidate with `INSERT DATA` (no delete) and assumes a fresh dataset. The `projecta_fuseki-data` volume persists across `docker compose` runs, so a previous run's confirmation left a second `candidateStatus asserted` on the same candidate; the SHACL `maxCount 1` constraint then rejects the duplicate. Runs that reuse the volume fail; runs after `docker compose --profile system-test down -v` pass.
**Fix / workaround:** Reset test state with `docker compose --profile system-test down -v` before re-running the system suite, or seed candidates idempotently (delete-then-insert). Diagnose by querying the candidate's statements in Fuseki (`SELECT ?p ?o WHERE { GRAPH <.../candidates/> { <candidate> ?p ?o } }`) and checking for duplicate `candidateStatus` values.
**Watch out for:** Any `mvn verify`/Compose system-test failure that reproduces the same SHACL violation on a reused volume but passes after `down -v` is a data-staleness issue, not a code or dependency regression. The API and Semantic Core system tests run in parallel against the same Fuseki, so avoid shared fixed candidate IDs between suites.

## [2026-08-04] Fuseki M4 updates need bound timestamps and graph-aware evidence joins

**Symptom:** The M4 rebuild endpoint first returned a safe 503 because Fuseki rejected `NOW()` in an INSERT template; after that was fixed, inferred blockers either materialized without evidence or were absent from retrieval.
**Root cause:** SPARQL Update expressions must be bound in the WHERE clause before insertion, template namespace formatting can silently produce a different IRI, and inferred `derivedFromAssertion` triples live in the inferred graph rather than the asserted graph.
**Fix / workaround:** Bind `NOW()` as `?time`, use explicit update delimiters, validate formatted IRIs in generated queries, and join inferred derivations from the inferred graph to asserted provenance before resolving candidate/source evidence.
**Watch out for:** Any new inference rule that uses generated timestamps, formatted namespace constants, or derived assertions must be exercised against a real Fuseki graph; mock gateway tests alone will not detect these graph-role and parser errors.

## [2026-08-04] Row-derived freshness misses empty and same-count inference drift

**Symptom:** M4 freshness could report an empty response as current and could miss asserted changes when the graph retained the same triple count and maximum timestamp.
**Root cause:** Freshness was inferred from returned derived rows, while the source revision used aggregate metadata rather than the asserted graph's actual RDF content.
**Fix / workaround:** Store a project-level inference snapshot marker and compare its source revision with a SHA-256 digest of sorted asserted RDF term tuples. Measure before and after retrieval to mark concurrent source changes partial and stale.
**Watch out for:** Never make snapshot health depend on result cardinality. Hashes over RDF with blank nodes require canonicalization; the current M4 asserted contract avoids blank nodes, so add a normalization algorithm before expanding that contract.

## [2026-08-09] Runtime gate working directories and health UI state are separate boundaries

**Symptom:** The root Sprint 7 validation script could not spawn Ruff, and the Settings screen showed an `unhealthy` connection notice while its health badge remained `unknown` until reload.
**Root cause:** The API gates inherited the repository-root environment instead of `apps/api`, while `SettingsScreen` only stored the connection result in the notice and did not merge it into the local profile state.
**Fix / workaround:** Run Ruff, Pyright, and Pytest from the API project directory with checked native exit codes; after a successful connection check, merge status, credential state, and check timestamp into the profile state. Assert the same response status in mocked and real browser journeys.
**Watch out for:** Real provider checks can take longer than mocked checks; real E2E should wait for the response and assert the badge against its returned status rather than hard-code a network-dependent outcome.

## [2026-08-09] Toolchain commands silently depend on their working directory

**Symptom:** Local validation initially failed to spawn Ruff from the repository root, and the GitHub Actions workflow failed immediately with `No pyproject.toml found in current directory or any parent directory`.
**Root cause:** Commands were grouped by task name rather than by the project boundary that owns their configuration. The Python toolchain resolves `pyproject.toml`, `uv.lock`, pytest configuration, and installed tools from `apps/api`; the web toolchain resolves `package.json`, lockfile, and scripts from `apps/web`; Compose and repository scripts belong at the repository root.
**Fix / workaround:** Maintain an explicit command-to-directory matrix: run `uv sync`, `uv run ruff`, `uv run pyright`, and `uv run pytest` from `apps/api`; run `npm ci` and web npm scripts from `apps/web`; run `docker compose`, cross-project PowerShell scripts, and repository-wide checks from the repo root. Mirror the same `working-directory` declarations in CI and use checked exit-code wrappers for native commands.
**Watch out for:** A command may work locally because of an activated environment or cached tool, while CI fails at project discovery. Before changing dependencies, verify the command's owning `pyproject.toml`/`package.json` and its working directory in both local scripts and workflow YAML.

## [2026-08-09] Same-length provider and reverse-proxy timeouts produce premature 504s

**Symptom:** Quick Note extraction returned an Nginx `504 Gateway Timeout` after
60 seconds while the API liveness endpoint remained healthy and the extraction
POST had no completed API access-log entry.
**Root cause:** Each provider attempt had a 60-second timeout and the API allowed
two bounded retries, but the same-origin Nginx proxy retained its default
60-second read timeout. The proxy closed the browser request while the API was
still completing or retrying the first provider attempt.
**Fix / workaround:** Set `proxy_read_timeout` and `proxy_send_timeout` to 210
seconds in the `/v1/` location, covering three 60-second attempts plus retry and
downstream overhead, and enforce a minimum 181-second proxy budget with
`npm run check:nginx-config`.
**Watch out for:** Any change to provider attempt timeout, retry count, backoff,
or an upstream proxy/load-balancer timeout must preserve an outer timeout larger
than the complete bounded operation budget so API problem responses are not
replaced by infrastructure-generated HTML errors.
