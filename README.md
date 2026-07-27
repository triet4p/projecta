# Projecta

Ontology-driven project intelligence for BrSE and project coordination workflows.

## Status

Projecta is currently in the architecture and semantic-foundation stage. The repository contains the approved initialization documents and agent governance; executable application services have not been implemented yet.

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

The target stack and repository layout are documented in `06-Tech-Stack.md`. Local and early-production deployment use the Compose-first approach in `08-Deployment-Choice.md`. Commands will be added when their executable configuration is introduced.

## License

Licensed under the [Apache License 2.0](LICENSE).
