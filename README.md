# Projecta

Ontology-driven project intelligence for BrSE and project coordination workflows.

## Status

Projecta is currently in the semantic-foundation stage. The Sprint 1 ontology
kernel, demo graph, competency queries, negative fixtures, and containerized
Jena validation are implemented and pass automated review. Ontology v0.1 is
approved as the repository-local semantic baseline; public w3id.org registration
is deferred. Application services have not been implemented.

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

## Repository Guidance

Read [AGENTS.md](AGENTS.md) before contributing. It defines source precedence and routes contributors to the applicable rules, skills, decisions, and initialization documents.

Agent resources are maintained under `.agents/`:

- Decisions: `.agents/memory/decisions.md`
- Contributor rules: `.agents/rules/`
- Project-specific skills: `.agents/skills/`

Do not duplicate their instructions in other contributor documents.

## Development Direction

Theo dõi roadmap và sprint đang hoạt động tại [Project Plan](docs/PLAN.md).

The first recommended vertical slice is:

```text
Quick Note
→ Candidate extraction
→ SHACL validation
→ Human confirmation
→ Asserted RDF
→ Rule inference
→ Project context query
```

The target stack and repository layout are documented in `06-Tech-Stack.md`. Local and early-production deployment use the Compose-first approach in `08-Deployment-Choice.md`.

Validate the current semantic artifacts with:

```text
docker compose run --build --rm ontology-test
docker compose -f compose.yaml -f compose.dev.yaml config
```

## License

Licensed under the [Apache License 2.0](LICENSE).
