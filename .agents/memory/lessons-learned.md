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

## [2026-08-09] Evidence projection renamed a live M2 field

**Symptom:** The real Compose M2 HTTP acceptance failed with `KeyError: sourceText` after the evidence endpoint returned only `evidenceText`.
**Root cause:** The API projection normalized the Semantic Core `sourceText` field to the newer `evidenceText` name without preserving the existing M2 acceptance contract.
**Fix / workaround:** Preserve both aliases in the public evidence item, sourcing either name from the downstream row, and cover both fields in projection tests.
**Watch out for:** Projection changes cross versioned HTTP contracts; run the real M2 lifecycle after renaming or consolidating a field.

## [2026-08-10] Graph filter query was mistaken for an evidence endpoint

**Symptom:** The deterministic browser Graph journey received a client-side
`API collection response is malformed` error even though the mocked Graph
projection contained valid `nodes`, `edges`, and `stale` fields.
**Root cause:** The response validator searched the complete URL for the
substring `evidence`; the valid Graph query parameter `evidence=any` therefore
matched the separate `/evidence` endpoint collection rule.
**Fix / workaround:** Match endpoint path segments (`/evidence` and `/current`)
instead of unqualified substrings, and keep a client regression test that calls
`getProjectGraph` with its default evidence filter.
**Watch out for:** Validators that inspect URLs must distinguish route segments
from query keys; add a regression whenever a new filter shares a route-word.

## [2026-08-10] Healthy containers can still hide a broken first domain read

**Symptom:** Clean-volume Compose reported healthy API, Semantic Core, Fuseki,
and web containers, but the production Projects screen returned a correlated
409. The acceptance script also initially failed on Windows PowerShell before
startup and later caught an internal graph IRI in bootstrap logs.
**Root cause:** Readiness still validated the removed single-project experience
setting instead of the server-owned catalog contract; clean Fuseki had no
explicit project fixture; the script used a newer .NET-only random API; and the
bootstrap success message printed its internal graph IRI. Health and narrow
mocked browser checks did not exercise this combined boundary.
**Fix / workaround:** Validate the explicit catalog plus server-owned actor,
seed named projects only through an acceptance-only fixture, generate random
bytes through the portable `RandomNumberGenerator.Create().GetBytes()` API,
redact bootstrap destinations, and run the first real catalog/selection/Graph
journey after restart before claiming clean-volume success.
**Watch out for:** Container health is necessary but not sufficient. Every
release acceptance should execute at least one real domain read through the
production proxy and inspect correlated logs, including on the supported host
shell.
## [2026-08-10] A declared single attempt can still contain SDK retries

**Symptom:** One Assisted Import stayed open until the 70-second proxy timeout,
the provider dashboard charged three identical input payloads, output tokens
were several times larger than input, and the browser received an HTML 504
without the API correlation header.

**Root cause:** OpenAI Python SDK 2.52.0 defaults to two retries, so Projecta's
one-attempt resilience policy actually produced one initial request plus two
hidden retries. The 60-second SDK timeout was slightly shorter than DeepSeek's
65-second thinking response, and DeepSeek V4's undocumented `/responses`
compatibility ignored `thinking.type=disabled`. Nginx also generated a request
ID for logging but forwarded the possibly empty client header to the API.

**Fix:** Set `max_retries=0` on every production SDK client and enforce one
outer `asyncio.timeout` deadline. Route `deepseek-*` through the documented Chat
Completions JSON contract with thinking disabled and a finite output cap. Make
Assisted Import request only entities, have the server derive evidence offsets
from exact text plus an explicit occurrence, and forward Nginx's canonical
request/operation IDs. Keep the proxy budget just outside the API deadline and
return correlated problem JSON for 504s.

**Prevention:** AST-test every production `AsyncOpenAI` constructor for
`max_retries=0`; test deadline cancellation, token-limit truncation, reasoning
usage, proposal-only schema, deterministic evidence derivation, Nginx syntax,
and correlation-header forwarding. A provider dashboard showing N identical
cache/input counts is evidence of N outbound calls, not one unusually large
call.

## [2026-08-10] Proxy response correlation can diverge from server-owned context

**Symptom:** The Projects catalog returned HTTP 200 with valid JSON, but the UI
rejected it with `The API success response correlation is invalid`.
**Root cause:** Experience middleware intentionally replaced the browser's
correlation hint with a server-owned `experience-*` ID in the response body and
upstream header. Nginx then hid that upstream header and replaced it with the
browser ingress ID, so the header and body disagreed.
**Fix / workaround:** Preserve the upstream `X-Request-Id` on every API-authored
response. Add an ingress correlation header only inside the named Nginx location
that authors proxy-timeout problem responses.
**Watch out for:** Never apply `proxy_hide_header X-Request-Id` or a location-wide
`add_header X-Request-Id` when an upstream service owns canonical correlation.
Test the actual response header against the JSON `requestId`, not merely that
both values exist independently.

## [2026-08-10] Persisted RDF can disappear behind a mismatched read projection

**Symptom:** A committed structured Note appeared in Notes and catalog counts
reported three candidates, but Graph and Review Queue were both empty.
**Root cause:** The writer stored Note labels as `name`, NoteItem labels as
`contentText`, and manual candidate type/label through the source NoteItem. The
read projection queried only asserted/candidate graphs and required every
candidate to have its own `rdfs:label` and semantic RDF type.
**Fix / workaround:** Project Note and NoteItem explicitly from the source graph,
join manual candidates to their canonical source items, and map the released
NoteItem type vocabulary to semantic candidate types. Keep the stored RDF
unchanged and make the projection accept both manual and LLM candidate shapes.
**Watch out for:** Persistence tests must exercise writer-to-reader compatibility
against a real Fuseki dataset. Entity counts and isolated writer tests cannot
prove that Graph or Review Queue can actually render the stored shape.

## [2026-08-10] Transport metadata broke strict node-detail validation

**Symptom:** Graph rendered correctly, but selecting any node returned HTTP 500
and the UI displayed `The operation failed safely` with a correlation ID.
**Root cause:** The private Semantic Core HTTP adapter appended
`_projecta_http_status` to successful payloads. The node-detail projection spread
the complete payload into `GraphNodeDetail`, whose Pydantic contract correctly
forbids extra fields, so the internal transport field caused validation failure.
**Fix / workaround:** Copy the node payload and remove the reserved transport
metadata before strict domain validation. Reproduce the real adapter shape in
both projection and HTTP route tests, then exercise every returned node handle.
**Watch out for:** Private status/correlation metadata must be consumed at the
transport boundary and never passed wholesale into `extra="forbid"` models.

## [2026-08-10] Compose interpolation can fail before a test service starts

**Symptom:** The clean system-test runner exited before creating any container
because Compose required `PROJECTA_API_SECRET_STORE_MASTER_KEY`, even though the
selected ontology test service did not consume that setting directly.
**Root cause:** Compose interpolates required variables across the complete
model before applying the selected profile/service. The runner generated only
the trusted-context secret, and it also restored required variables before its
final `compose down` command.
**Fix / workaround:** Generate a process-scoped valid Fernet master key alongside
the trusted-context secret, keep both variables set through Compose cleanup,
then restore their exact prior environment state in `finally`.
**Watch out for:** Every Compose acceptance script must satisfy all required
model interpolation variables before its first Compose command and preserve
them until the last cleanup command, including on failure paths.

## [2026-08-10] API-only defaults can break a strict downstream payload

**Symptom:** The real HTTP confirmation journey expected a finite `409`, but the
API returned `503 SEMANTIC_CONTRACT_UNAVAILABLE` while Semantic Core logged only
the operation start.
**Root cause:** Pydantic materialized the API-only default
`correctionRevision: 0`, and the legacy route forwarded the complete public
request model to Semantic Core. Its strict Java request record accepted only
`assertion`, so Javalin emitted a plain 500 response that the API correctly
rejected as an invalid downstream contract.
**Fix / workaround:** Build the private Semantic Core payload explicitly from
the allowlisted `assertion` field and add a regression that asserts the exact
forwarded body. Preserve failure-time Compose logs before cleanup so a transport
normalization error can be traced to its originating boundary.
**Watch out for:** Never forward a complete public DTO across a private service
boundary when it contains defaults, UI metadata, or fields owned by another
layer. Construct and test the downstream DTO field by field.

## [2026-08-10] Connector migration history can contain a column already in the base revision

**Symptom:** A clean isolated Compose migration failed with `DuplicateColumn`
when the revision migration added `connector_sync_runs.revision`.
**Root cause:** The initial migration already contained the column while the
follow-up migration still assumed a legacy initial schema without it.
**Fix / workaround:** Make the follow-up migration inspect the live table and
add/drop the column only when the requested shape is actually absent/present,
so both fresh and legacy migration histories converge safely.
**Watch out for:** When a model change lands before migration history is
finalized, run `upgrade head` on a clean database and on the existing local
volume; do not assume the revision script's stated prior shape matches the
checked-in initial migration.

## [2026-08-11] PowerShell native stderr can abort passing gates

**Symptom:** Sprint validation and recovery runners stopped on passing Python/Alembic/docker commands whose normal progress was written to stderr; recovery cleanup also surfaced a missing-container error after an earlier gate stopped.
**Root cause:** PowerShell's `$ErrorActionPreference=Stop` promoted captured native stderr records to terminating errors before the runner evaluated the native exit code, and cleanup assumed every later container had been created.
**Fix / workaround:** Temporarily capture native gates with `ErrorActionPreference=Continue` and `$PSNativeCommandUseErrorActionPreference=$false`, decide success only from `$LASTEXITCODE`, and make cleanup tolerant of absent containers.
**Watch out for:** Any PowerShell gate that uses `2>&1` around Python, Docker, or migration tools must isolate stream handling while preserving explicit exit-code checks.

## [2026-08-11] Fuseki HTTP request logs can expose RDF graph IRIs

**Symptom:** Clean-Compose functional journeys passed, but the safe-log gate found an ontology IRI in Fuseki output.
**Root cause:** Fuseki's `org.apache.jena.fuseki.Fuseki` INFO logger emitted request URLs, including the graph query parameter used by ontology bootstrap.
**Fix / workaround:** Added an image-local `log4j2.properties` configuration that keeps root INFO logging, sets the Fuseki HTTP logger to WARN, disables the NCSA request logger, and retained a Compose contract test for the configuration.
**Watch out for:** Request URLs and query parameters are payload-bearing at RDF boundaries; do not rely on `--quiet` alone or remove ontology/fixture tokens from the denylist.

## [2026-08-11] A global event primary key breaks project-scoped idempotency

**Symptom:** The deterministic fixture reused `evt-001` per installation, but a
second project could conflict with or replay the first project's event.
**Root cause:** The inbox contract defined event identity as project,
installation, and event ID, while the PostgreSQL primary key and conflict target
used only `event_id`.
**Fix / workaround:** Use the composite identity `(project_id,
installation_id, event_id)` consistently in the primary key, foreign keys,
repository conflict target, completion predicates, and concurrency tests.
**Watch out for:** A project predicate on reads does not make an identifier
project-scoped when uniqueness is still enforced globally at write time.

## [2026-08-11] Source projection filters can silently hide connector candidates

**Symptom:** A real connector import appeared in Graph as a Note and NoteItem,
but Review Queue reported no pending candidates.
**Root cause:** Capture correctly wrote connector candidates with generator
`connector-json-mock-v1`, while the shared candidate projection selected only
generator `manual-quick-note-v0.3.0`.
**Fix / workaround:** Keep the existing source-item projection and explicitly
allow both governed generator values; verify the real import through Graph and
Review Queue in clean Compose.
**Watch out for:** Writer tests and Graph visibility do not prove candidate
reviewability. Every new source kind must be exercised through the actual shared
candidate query and browser queue.

## [2026-08-11] Browser gates must not rewrite tracked evidence

**Symptom:** Every functional and security gate passed, but the exact release
commit ended with a dirty worktree because a deterministic Playwright test
overwrote a Sprint 8 screenshot under `docs/`.
**Root cause:** The test used a repository-relative tracked evidence path for a
runtime screenshot, so normal validation mutated source state even though the
test itself passed.
**Fix / workaround:** Write runtime screenshots through
`testInfo.outputPath(...)`, which stays under Playwright's ignored
`test-results` directory, and enforce the boundary with a release-contract
test.
**Watch out for:** An immutable preflight must verify the worktree again after
all gates. Passing tests are insufficient when test runners can rewrite tracked
snapshots, generated clients, lockfiles, or evidence artifacts.

## [2026-08-11] Legacy Compose runners must track new required variables

**Symptom:** The tag-triggered `system` job failed before creating a container,
even though the Sprint 10 validation, acceptance, and recovery runners passed
locally and the dedicated validation/acceptance workflow jobs passed.
**Root cause:** Sprint 10 made the connector PostgreSQL user, password, and
database required across the Compose model. The older `run_system_tests.ps1`
runner still generated only trusted-context and master-key values, so Compose
failed during whole-model interpolation.
**Fix / workaround:** Give every Compose entry point an isolated connector
database environment before its first Compose command, retain it through
cleanup, restore the caller's exact prior values, and enforce those variable
names in the release-workflow contract suite.
**Watch out for:** Adding a required Compose interpolation variable is a
cross-runner contract change. Audit every script and CI job that parses the
model, including older profiles that do not directly start the new service.

## [2026-08-11] Local-contract tests must be collection-safe in runtime images

**Symptom:** A container suite excluded repository-source tests with
`-m "not local_contract"`, but pytest still failed while importing those tests.
**Root cause:** Pytest imports modules before marker selection, and two modules
computed a repository parent path at module scope that did not exist under the
image's shallow `/app` layout.
**Fix / workaround:** Mark repository-source checks as `local_contract` and
defer repository-root discovery until the test function executes.
**Watch out for:** A deselected test can still break collection through module
imports, constants, decorators, fixtures, or other module-scope evaluation.

## [2026-08-11] Docker published ports may have multiple bindings

**Symptom:** The recovery drill passed with Docker Desktop but failed on a Linux
CI runner with `Cannot index into a null array` after PostgreSQL became ready.
**Root cause:** `docker port` returned separate IPv4 and IPv6 mappings. In
PowerShell, regex matching a string array filters the array but does not populate
the scalar `$Matches` table used by the runner.
**Fix / workaround:** Capture mappings as an array, join them, use
`[regex]::Match`, validate `Success`, and read the named capture group from the
match object.
**Watch out for:** Treat Docker CLI output as multi-line on every platform;
never couple parsing to PowerShell's scalar-only `$Matches` side effect.

## [2026-08-13] Official production images need runtime-specific writable paths and commands

**Symptom:** The clean production-shaped Compose run failed in sequence with OpenBao `permission denied` on `vault.db`, PostgreSQL bootstrap errors, Keycloak restart loops, and an OpenBao healthcheck that never became healthy.
**Root cause:** The pinned OpenBao image runs as UID 100 and owns `/openbao/file`, while the override mounted a new volume at `/openbao/data`; the official CLI binary is `bao`, not `openbao`; the PostgreSQL init script omitted the configured database role for `createdb`; and the unbuilt official Keycloak image cannot first-start with an immutable root filesystem and `--optimized`.
**Fix / workaround:** Store Raft data at `/openbao/file`, use `bao` with a TLS hostname matching the certificate, pass `--username "$POSTGRES_USER"` to `createdb`, start Keycloak without `--optimized`, and allow the official image to perform its first-start build before hardening it in a prebuilt image pipeline.
**Watch out for:** Pinning an official digest is not equivalent to using the repository's locally built image. Validate entrypoint names, prebuilt/runtime assumptions, volume ownership, healthcheck TLS SANs, and required Compose environment roles with a disposable clean-volume run.

## [2026-08-13] Long Alembic revision IDs fail only on a real migration ledger

**Symptom:** Unit and static migration tests passed, but a clean PostgreSQL
migration failed after applying the DDL with `value too long for type character
varying(32)` while updating `alembic_version.version_num`.
**Root cause:** The new revision ID `0005_identity_sessions_memberships` was
longer than Alembic's default 32-character version column. SQLite/model tests
did not exercise the PostgreSQL version-ledger update.
**Fix / workaround:** Keep the descriptive migration filename, but use the
bounded revision ID `0005_identity_sessions` and update the next migration's
`down_revision`; verify from an empty PostgreSQL volume.
**Watch out for:** Check every Alembic `revision` and `down_revision` against
the deployed version-column width, and retain a clean real-database migration
gate rather than relying only on schema/unit tests.

## [2026-08-13] OpenBao automation can silently target the wrong API contract

**Symptom:** Recovery automation initialized OpenBao but later received empty
recovery-key or AppRole values, even though a subsequent command made the
overall gate appear successful.
**Root cause:** OpenBao 2.6.1 emits `unseal_keys_b64`, the RoleID endpoint ends
in `/role-id`, and AppRole must be explicitly enabled before its role is
written. A multi-command PowerShell gate checked only the last native exit code.
**Fix / workaround:** Read `unseal_keys_b64`, use
`auth/approle/role/<role>/role-id`, enable `approle`, and make every `bao`
invocation throw immediately on a nonzero exit code.
**Watch out for:** Never treat the final exit code of a group of operator
commands as proof that all earlier secret-manager mutations succeeded.

## [2026-08-13] PowerShell can split dotted Docker command arguments

**Symptom:** A direct OpenBao container exited with `a storage backend must be
specified` although the config bind mount existed and the command visibly used
`-config=/openbao/config.hcl`.
**Root cause:** PowerShell native argument passing split the dotted argument
into `-config=/openbao/config` and `.hcl`.
**Fix / workaround:** Build Docker invocations as a string argument array and
call `docker @arguments`; confirm the resulting `.Config.Cmd` when debugging.
**Watch out for:** Direct Windows PowerShell calls that pass dotted paths or
flag-value expressions to a Linux container, especially acceptance/recovery
runners that do not go through Compose.

## [2026-08-13] pg_dumpall clean restores report unavoidable system-object errors

**Symptom:** A complete PostgreSQL restore stopped before recreating application
databases when `psql -v ON_ERROR_STOP=1` processed a `pg_dumpall --clean` file.
**Root cause:** The dump necessarily attempts to drop the connected `postgres`
database and current superuser, which a live restore session cannot do.
**Fix / workaround:** Let the dump continue past those system-object errors,
then fail closed with database-specific verification: Projecta rows/session
state, replay/evidence integrity, and Keycloak boot from the restored database.
**Watch out for:** Do not equate a zero-error `pg_dumpall --clean` transcript
with correctness; verify restored consumers and state explicitly.

## [2026-08-13] GitHub acceptance Compose requires a formatted project fixture and rebuilt migrations

**Symptom:** The acceptance stack stopped during Fuseki bootstrap with
`acceptance project fixture entry is invalid`, and the migration image stopped
at revision 0006 even though the repository contained revision 0007.
**Root cause:** `PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS` is parsed as
`project-id|label` entries, and an already-built local API image does not
automatically include newly added Alembic revisions.
**Fix / workaround:** Use a value such as `project-a|Project A`, rebuild the
`api` and `connector-migrate` targets, and start the disposable stack again.
**Watch out for:** Any new migration or acceptance project must be checked
against the Compose image build state before provisioning a setup handle.

## [2026-08-13] Live journey fixtures must preserve provider numeric widths

**Symptom:** The edit journey could create a synthetic issue, but its known
comment was not merged into the bounded snapshot because GitHub comment IDs can
exceed a 32-bit integer.
**Root cause:** PowerShell snapshot reconciliation cast provider IDs to
`Int32`, while GitHub returns larger numeric IDs.
**Fix / workaround:** Compare provider IDs as `Int64` and keep the live
snapshot sanitized to counts, hashes, and timestamps only.
**Watch out for:** Provider numeric identifiers are untrusted external data;
never narrow them to a platform `Int32` during pagination, deduplication, or
evidence generation.

## [2026-08-13] PowerShell REST exceptions can hide the HTTP status code

**Symptom:** The live edit journey received the expected forged-project `404`,
but its isolation field remained null and the journey failed closed.
**Root cause:** On this PowerShell/.NET path, `Invoke-RestMethod` exposed a
problem JSON body whose `status` was `404` while `Exception.Message` did not
contain the numeric status.
**Fix / workaround:** Inspect both the exception message and
`ErrorDetails.Message`, accepting the structured `status: 404` or
`CONNECTOR_NOT_FOUND` problem code for the isolation assertion.
**Watch out for:** Do not derive HTTP acceptance outcomes from
`Exception.Message` alone; preserve and validate the structured problem body,
especially when running the same PowerShell script across Windows versions.

## [2026-08-14] Release CI needs explicit test-environment and static-gate parity

**Symptom:** The `v0.6.0` release workflow failed before publishing even though
the local release validation passed: release-contract and Sprint 10 unittest
steps could not import `pytest`, and the Sprint 8 implicit-behavior gate rejected
an `except Exception` in Teams HTML sanitization.
**Root cause:** Two CI paths invoked the system Python without installing the
test dependency, while the local global environment already had `pytest`. The
local Sprint 11 validation did not include the Sprint 8 static implicit-behavior
check, so the broad catch was not detected before tagging.
**Fix / workaround:** Install `pytest` in the release-contract job, run Sprint
10 release-contract tests through the API project's locked `uv` environment,
and catch only the parser exceptions that the sanitization boundary is intended
to absorb.
**Watch out for:** Any release workflow job that imports `pytest` must bootstrap
its test environment explicitly, and every new broad exception handler must be
checked against the Sprint 8 implicit-behavior gate before creating a release
tag.

## [2026-08-14] Revalidate local immutable image references after Compose builds

**Symptom:** A clean Compose rerun attempted to pull the local API image from a
nonexistent registry even though the same image had passed an earlier run.
**Root cause:** The Compose integration-test build refreshed the local API image
ID, so the previously captured `projecta-api@sha256:...` reference no longer
matched the local image available to the daemon.
**Fix / workaround:** Inspect the current local image ID after every Compose
build and use that exact digest reference for the next immutable preflight; do
not assume a prior local digest remains valid after a test image rebuild.
**Watch out for:** Keep image digest capture and Compose execution in the same
validated preflight sequence, especially when `--build` creates connector test
images from the same Docker context.

## [2026-08-14] Release gates must normalize artifact bytes and build local-only images

**Symptom:** Linux CI rejected the G2 journey waiver because the packet used a
Windows CRLF file hash, and the clean acceptance runner tried to pull the
repository-local Fuseki image from a registry. The real Compose browser journey
also stopped at the unauthenticated shell in local experience mode.
**Root cause:** The repository validator hashed platform-dependent bytes, the
acceptance script relied on `up --build` to materialize an image used by a
separate bootstrap service, and experience-mode auth sessions did not expose
the server-owned context to the new browser auth shell.
**Fix / workaround:** Normalize CRLF to LF before hashing the journey artifact,
build the Fuseki image explicitly before starting the acceptance topology, and
return an authenticated server-owned experience session only when the explicit
experience actor and trusted context are configured.
**Watch out for:** Release evidence digests must be computed from canonical
bytes; every local-only Compose image used by another service needs an explicit
build step; and experience mode must remain closed unless its server-owned
context configuration is complete.
