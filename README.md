# Projecta

Ontology-driven project intelligence for BrSE and project coordination workflows.

## Status

Projecta has completed M1 (the executable semantic foundation), M2 (the
Manual Quick Note slice), M3 (the LLM extraction slice), and M4 (project-scoped
retrieval and coordination). Sprint 7 adds the first usable React web
experience and user-managed runtime configuration. Ontology v0.1, v0.2, v0.3,
and the additive v0.4 candidate vocabulary are approved repository-local
releases.

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
- A same-origin Compose web boundary serves the React SPA and proxies only the
  public Application API and health routes; the browser does not call Semantic
  Core or Fuseki directly.
- The local experience supports encrypted, redacted LLM profile management,
  connection checks, credential rotation/removal, typed evidence capture,
  candidate review, current Requirements, evidence/history inspection, and
  grounded project Q&A.

Sprint 7 source validation and browser acceptance pass on the local stack;
S7-47/M5 product and security acceptance remains a human review gate.
Authentication/authorization, connectors, public deployment, pagination, and
general edit/delete workflows remain out of scope. See the [project plan](docs/PLAN.md),
[Sprint 7 review packet](docs/sprint-plans/sprint-7/review-packet.md), and
[local experience runbook](docs/runbooks/sprint-7-local-experience.md) for
delivery evidence and operating boundaries.

## Try the current app

The supported local experience is a disposable Compose deployment. It does
not require `PROJECTA_LLM_*` variables on first start; configure the provider
from **Settings** after the web app opens.

From PowerShell, set the two deployment-owned secrets and start the web
profile:

```powershell
$env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = (New-Guid).Guid
$env:PROJECTA_API_SECRET_STORE_MASTER_KEY = uv run --project apps/api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker compose -f compose.yaml -f compose.dev.yaml --profile web up --build
```

Open <http://localhost:3000>. The main journey is:

1. **Settings** — enter a compatible provider URL, model, and credential;
   save the profile, test the connection, or rotate/remove the credential.
   The credential field is cleared after submission and the browser receives
   only redacted profile metadata.
2. **Capture** — select an exact span from a note and create typed evidence
   without configuring an LLM.
3. **Review** — validate the candidate against SHACL, then confirm it as a
   `Requirement` or reject it. Confirmation is always an explicit human action.
4. **Knowledge** — inspect current Requirements, open their evidence, and load
   candidate history using the opaque candidate ID shown in the active workflow.
5. **Q&A** — ask a bounded project question and receive a grounded answer with
   citations, derivation, or a safe abstention when the graph lacks support.
6. **Diagnostics** — inspect local API/Semantic Core readiness and experience
   mode without exposing deployment secrets or graph internals.

Quick Note extraction is also available from **Extract** after a compatible LLM
profile is configured. If the provider is unavailable, the connection status
is shown safely and extraction fails closed; typed capture remains available for
the evidence and review journey.

Stop the local app with:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile web down
```

For a disposable reset that also removes the local operational volumes, use
`down --volumes --remove-orphans` only when the data is no longer needed.

## Current validation commands

Run the source-level gates from the repository root; the script enters each
project directory explicitly:

```powershell
pwsh -File scripts/run_sprint7_validation.ps1
```

Run real browser acceptance against an isolated Compose project. The script
builds the stack, tests before and after an API/web restart, and cleans its
containers, network, and volumes:

```powershell
pwsh -File scripts/run_sprint7_acceptance.ps1
```

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

The implemented M3/M4 and Sprint 7 slice is:

```text
Quick Note
→ LLM extraction or deterministic replay
→ Normalization and exact Unicode evidence validation
→ SHACL validation
→ Human confirmation or rejection
→ Asserted RDF and provenance
→ Project-scoped reads and grounded Q&A
→ React web experience over the Application API
→ Encrypted operational settings and redacted browser responses
```

Inference and ontology evolution remain governed boundaries; S7 exposes the
released project-context retrieval and evidence contracts without exposing raw
graph IRIs to the browser.

The target stack and repository layout are documented in `06-Tech-Stack.md`. Local and early-production deployment use the Compose-first approach in `08-Deployment-Choice.md`.

Validate the current semantic artifacts with:

```text
docker compose run --build --rm ontology-test
docker compose -f compose.yaml -f compose.dev.yaml config
```

Historical Sprint 5 gates (API tests, replay evaluation, and the Compose E2E
chain) can still be run with:

```text
pwsh -File scripts/run_sprint5.ps1
```

The live provider quality gate is opt-in and credential-gated:

```text
pwsh -File scripts/run_sprint5.ps1 -RunLive
```

## License

Licensed under the [Apache License 2.0](LICENSE).
