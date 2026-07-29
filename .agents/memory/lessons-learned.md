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
