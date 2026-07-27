# Projecta Source Map

Use project documents as authoritative sources. This file routes reading; it does not replace them.

## Always read

- `docs/initialization/05-Ontology-Design.md` — read completely. It defines competency-question-driven design, modules, preliminary hierarchy/properties, SHACL, named graphs, lifecycle, inference, temporal modeling, identity, versioning, testing, and governance.

## Read for every semantic change

- `docs/initialization/01-Project-Overview.md`
  - Product vision and target users.
  - Core values.
  - Architecture principles and success criteria.
- `docs/initialization/02-Project-Scope.md`
  - Domain entities.
  - Semantic Core scope.
  - Human-in-the-loop requirements.
  - Security/governance.
  - Boundary decisions and delivery-slice strategy.
- `docs/initialization/03-Project-Architecture-Overview.md`
  - Semantic Core responsibilities.
  - Data flow.
  - Named graph strategy.
  - Trust model and invariants.
- `docs/initialization/04-Memory-Layer.md`
  - Authority of each memory type.
  - Candidate/asserted/inferred/evidence separation.
  - Synchronization, rebuild, and isolation rules.

## Read when implementing artifacts

- `docs/initialization/06-Tech-Stack.md`
  - Jena/Fuseki/TDB2 runtime.
  - Repository structure and test tooling.
- `docs/initialization/07-Learning-Path-Index.md`
  - Phases 1–3.
  - Build-and-learn loop.
  - First vertical slice.

## Read when runtime or deployment is affected

- `docs/initialization/08-Deployment-Choice.md`
  - Container and environment parity.
  - TDB2 ownership, backup, and deployment constraints.

## Precedence

Apply sources in this order:

1. Current explicit human instruction.
2. Repository instructions and approved decision records.
3. Initialization documents.
4. Existing released ontology and migrations.
5. This skill.

If two project sources conflict, surface the conflict and avoid silently selecting a production semantic meaning.
