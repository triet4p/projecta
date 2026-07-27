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
