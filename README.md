# Projecta

Ontology-driven project intelligence for BrSE and project coordination workflows.

## Status

Projecta has completed M1 (the executable semantic foundation), M2 (the
Manual Quick Note slice), and M3 (the LLM extraction slice). Ontology v0.1,
v0.2, v0.3, and the additive v0.4 candidate vocabulary are approved
repository-local releases.

The current working vertical slice is:

- FastAPI accepts an untyped Quick Note and produces typed entity, relation,
  and same-project link candidates through a provider-neutral LLM gateway
  (live provider or deterministic replay).
- The Semantic Core atomically records source notes, exact-evidence
  candidates, and provenance in project-scoped graphs, and enforces the v0.4
  SHACL contract at the mutation boundary.
- Candidates can be validated, confirmed, or rejected through the API.
  Abstentions are persisted as auditable extraction provenance.
- Confirmed candidates produce asserted Requirements; rejected candidates do
  not create asserted items; no model output is ever asserted automatically.
- Capture, extraction, and review retries are idempotent, with transaction
  rollback, project isolation, and restart persistence covered by tests.

The canonical Sprint 5 suite passed 119/119 ontology checks, Semantic Core
35/35 tests, 51/51 API end-to-end tests, a clean offline replay evaluation
(all metrics `1.0`), and the live provider quality gate twice consecutively.
Authentication/authorization, connectors, public deployment, pagination, and
edit/delete workflows remain out of scope. See the [project plan](docs/PLAN.md)
and [Sprint 5 review packet](docs/sprint-plans/sprint-5/review-packet.md) for
the current delivery evidence.

## Vision

Projecta turns selected notes, messages, documents, research, and task-system events into structured project memory. Its semantic core separates candidate, asserted, and inferred knowledge, preserves provenance, and keeps humans responsible for domain assertions and consequential actions.

Microsoft Teams is an initial connector, not the system center. Connectors, LLM providers, retrieval indexes, and deployment infrastructure remain replaceable behind explicit contracts.

## Start Here

- [Documentation index](docs/initialization/README.md)
- [Project overview](docs/initialization/01-Project-Overview.md)
- [Scope and boundaries](docs/initialization/02-Project-Scope.md)
- [Architecture](docs/initialization/03-Project-Architecture-Overview.md)
- [Memory model](docs/initialization/04-Memory-Layer.md)
- [Ontology design](docs/initialization/05-Ontology-Design.md)
- [Technology stack](docs/initialization/06-Tech-Stack.md)
- [Build-and-learn path](docs/initialization/07-Learning-Path-Index.md)
- [Deployment choice](docs/initialization/08-Deployment-Choice.md)
- [Application API contract](docs/architecture/application-api.md)
- [Semantic Core API contract](docs/architecture/semantic-core-api.md)
- [Quick Note use case](docs/use-cases/quick-note.md)

## Repository Guidance

Read [AGENTS.md](AGENTS.md) before contributing. It defines source precedence and routes contributors to the applicable rules, skills, decisions, and initialization documents.

Agent resources are maintained under `.agents/`:

- Decisions: `.agents/memory/decisions.md`
- Contributor rules: `.agents/rules/`
- Project-specific skills: `.agents/skills/`

Do not duplicate their instructions in other contributor documents.

## Development Direction

Theo dõi roadmap và sprint đang hoạt động tại [Project Plan](docs/PLAN.md).

The implemented M3 slice is:

```text
Quick Note
→ LLM extraction or deterministic replay
→ Normalization and exact Unicode evidence validation
→ SHACL validation
→ Human confirmation or rejection
→ Asserted RDF and provenance
→ Project-scoped reads
```

Inference remains a preserved boundary, not a materialized output, until a
future milestone has an approved competency question and rule.

The target stack and repository layout are documented in `06-Tech-Stack.md`. Local and early-production deployment use the Compose-first approach in `08-Deployment-Choice.md`.

Validate the current semantic artifacts with:

```text
docker compose run --build --rm ontology-test
docker compose -f compose.yaml -f compose.dev.yaml config
```

Run the full Sprint 5 system suite (API tests, replay evaluation, and the
Compose E2E chain) with:

```text
pwsh -File scripts/run_sprint5.ps1
```

The live provider quality gate is opt-in and credential-gated:

```text
pwsh -File scripts/run_sprint5.ps1 -RunLive
```

## License

Licensed under the [Apache License 2.0](LICENSE).
