# Sprint 5 M3 Review Packet

Status: `RELEASE_BLOCKED_LIVE_QUALITY`

## Scope and boundary

Sprint 5 implements an untyped Quick Note extraction path. A provider may propose typed entity candidates, relation candidates, and bounded same-project links. The API normalizes and validates exact Unicode evidence, applies project-context checks, and sends candidates to Semantic Core as reviewable proposal data. No extracted proposal is an asserted fact, and no automatic assertion or external action is part of this sprint.

## Contract and version inventory

| Boundary | Version / artifact |
|---|---|
| Extraction response | `m3.v1` Pydantic contract |
| Prompt | `m3.prompt.v1` |
| Evaluation fixture | `s5.v1` / `evaluation/sprint-5/dataset.v1.json` |
| Replay fixture | `s5.replay.v1` |
| Provider route | OpenAI-compatible Responses API via configurable DeepSeek endpoint |
| Configuration | `PROJECTA_LLM_TYPE`, `PROJECTA_LLM_BASE_URL`, `PROJECTA_LLM_API_KEY`, `PROJECTA_LLM_MODEL` |
| Candidate ontology | Approved v0.4 additive vocabulary and shapes |

Provider reference: [DeepSeek Responses API guide](https://api-docs.deepseek.com/guides/responses_api).

## Implemented layers

- API contracts, prompt construction, provider-neutral gateway, replay gateway, OpenAI Responses adapter, bounded retries, telemetry schema, and orchestration.
- Semantic Core bounded link-context read and atomic candidate ingestion route.
- Entity, relation, and link normalization with exact source-span and project-boundary validation.
- Deterministic eight-case evaluation dataset, complete replay outputs, offline runner, and opt-in live runner.
- Canonical Sprint 5 runner: `scripts/run_sprint5.ps1`.
- Corrective implementation pass: exact evidence text is preserved separately
  from the proposed label, generated Turtle is parseable, idempotent replay
  parses SPARQL JSON structurally, and the bounded link-context read is exposed
  through the trusted API boundary.

## Validation evidence

- `docker compose config --quiet`: passed; API services receive all four required `PROJECTA_LLM_*` variables.
- Ontology container: canonical v0.1-v0.4 suite passed `119/119` checks.
- Local API: `49 passed, 2 skipped`; `ruff check`: passed; `pyright`: `0 errors, 0 warnings, 0 informations`.
- Canonical clean Compose system run: Semantic Core `35/35` tests passed via `mvn verify` and API E2E passed `51/51`; the runner cleaned its ephemeral project and volumes.
- Offline replay evaluation: `8` cases; schema validity, precision/recall/F1, exact spans, bounded cross-project rejection and abstention thresholds all passed at `1.0`.
- `mvn -q -DskipTests compile`: passed.
- `mvn -q -Dtest='*Test,!Tdb2LifecycleIntegrationTest' test`: passed.
- A prior DeepSeek run completed transport/schema processing for 8/8 cases, but completion is not a quality pass.
- The latest single-case probe returned a wrong entity type. Its prior non-exact-span finding is invalidated because the gold fixture incorrectly used end offset `45` for a 44-code-point sentence. The dataset, replay fixture, and evaluator gold-span validation are corrected; the live quality gate now requires an explicit rerun against that corrected baseline.

The full Maven suite has a known Windows-only TDB2 temporary-directory cleanup lock during teardown. No assertion failure was observed; the clean Linux container-backed `mvn verify` run passed.

## Governance and review questions

The v0.4 candidate vocabulary, shapes, fixtures, and competency queries remain human-approved for the Sprint 5 M3 contract. Runtime target closure, ontology allowlist, abstention provenance, atomic ingestion, replay idempotency, and canonical E2E execution are implemented and validated. There is no remaining implementation blocker. Release remains blocked only until the corrected live provider quality gate is rerun and passes or its result is explicitly accepted/revised.

1. Entity, relation, and link candidate classes belong in the v0.4 ontology.
2. Model, prompt, and schema versions are extraction-activity provenance metadata.
3. The candidate predicates, exact evidence, and same-project boundary are accepted.
4. The evaluation thresholds and provider configuration are accepted for Sprint 5.

## Rollback and isolation

The live provider path fails closed when required configuration is absent. Replay mode is deterministic and offline. Candidate ingestion is conditional and idempotent; validation failures occur before persistence. The approved v0.4 ontology is additive and remains compatible with the released v0.3 behavior; no existing-data migration is required.
