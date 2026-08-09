# Sprint 8 Operations — Health and Failure Diagnostics

## Truthful health states

- `/health/live` means the process is running and can answer diagnostics.
- `/health/ready` means the declared dependency and configuration contract is
  usable at that boundary.
- A live but not-ready container must remain unhealthy in Compose. It must not
  be converted into a successful empty response or a synthetic ready state.

## Inspect the exact probe evidence

Run from the repository root:

```powershell
docker compose ps
docker inspect --format '{{json .State.Health}}' projecta-api-1
docker inspect --format '{{json .State.Health}}' projecta-semantic-core-1
docker inspect --format '{{json .State.Health}}' projecta-fuseki-1
```

The `.State.Health.Log` entries retain the command, exit code, output, start,
and end time for each probe. Do not replace this evidence with a manual
`curl`-only success claim.

## Check boundaries in order

```powershell
docker compose logs --no-color --tail=200 fuseki
docker compose logs --no-color --tail=200 semantic-core
docker compose logs --no-color --tail=200 api
Invoke-WebRequest http://localhost:8000/health/live
Invoke-WebRequest http://localhost:8000/health/ready
```

For the Web container, inspect both the Web liveness endpoint and the API
proxy logs. A `503` readiness result is an explicit dependency/configuration
failure; it is not permission to restart blindly, switch provider, or use a
fallback project.

## Required failure evidence

When a service is not ready, record:

1. The service name and Compose profile.
2. The probe command and latest exit code/output from `Health.Log`.
3. The correlated `requestId`/`operationId` and finite problem code, when an
   HTTP request reached the service.
4. The first failed dependency in the chain: Fuseki, Semantic Core, API
   configuration, provider profile, or Web proxy.

Never paste secrets, trusted context headers, provider payloads, prompts, raw
Note text, SPARQL, RDF, graph IRIs, or stack traces into an incident record.

## Bootstrap and project selection

Use the production web profile with explicit server configuration. Experience
mode requires a finite server-owned catalog; an empty catalog fails closed.

```powershell
$env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = '<deployment-secret>'
$env:PROJECTA_API_SECRET_STORE_MASTER_KEY = '<fernet-key>'
$env:PROJECTA_API_RUNTIME_MODE = 'experience'
$env:PROJECTA_API_EXPERIENCE_PROJECT_CATALOG = 'project-alpha,project-beta'
docker compose --profile web up -d --build
```

The browser starts at Projects, calls the catalog boundary, and selects a
visible project using its server-issued opaque handle plus catalog revision.
The browser must not send trusted project/actor headers, remember a raw
project ID, or fall back to a local project after a stale selection. Use Change
project to clear the active workspace and select again from the catalog.

## Structured Note workflow

In the selected workspace, open Notes or New Note:

1. Add ordered typed NoteItems and source content; duplicate content is valid
   and remains distinct by position.
2. Save draft. Empty drafts are allowed while editing; the server derives
   canonical `rawText` and Unicode code-point offsets.
3. Use assisted import only to load editable proposals. Import never commits
   automatically; an explicit abstention is a successful visible outcome.
4. Commit only after the draft is non-empty and ready. The source Note remains
   evidence; candidate review and asserted knowledge are separate lifecycle
   boundaries.

The public boundary is documented in
`docs/architecture/structured-note-api.md`. The browser uses
`/v1/projects/{handle}/notes/drafts`, `/notes/import`, `/notes`, and the
draft commit endpoint; opaque handles are display/navigation tokens, not user
input fields.

## Graph and review operations

Graph is a bounded projection, not an RDF browser. Use finite filters, the
accessible companion table, and one-hop expansion. Each node exposes label,
semantic type, lifecycle, verification, provenance, evidence count, freshness,
and available actions. Empty, stale, partial, and unavailable states are
distinct; never infer a failed query from an empty table.

Review Queue lists labeled candidate handles without asking the operator to
type one. Select a candidate, validate it, optionally save an audited
structured correction, then explicitly confirm or reject. Revalidation is
required after correction. Evidence and history traversal must remain inside
the selected project scope.

Q&A accepts a bounded natural-language question and returns answer completeness,
warnings, facts, and citations. It does not accept SPARQL or arbitrary graph
filters. A partial/abstained answer is not the same as a transport failure.

## Errors, correlation, retry, and recovery

Every response carries `X-Request-Id`; mutation requests also carry an
operation/idempotency boundary. Public errors are finite
`application/problem+json` contracts with `code`, safe `detail`, and the
correlation ID. Record the service, route class, timestamp, request ID,
operation ID, HTTP status, and problem code—not payloads or secrets.

Use one explicit retry after checking the correlated failure and current
readiness. Do not retry a mutation by refreshing, changing provider, switching
project, or submitting a new idempotency key. Resolve stale revisions by
reloading the selected project/draft and asking the operator to review the
new state. Resolve a not-ready service from the first failing dependency in
the health chain, then rerun the original user action explicitly.

| Problem state | Operator action | Prohibited fallback |
| --- | --- | --- |
| `PROJECT_SELECTION_REQUIRED` or stale selection | Return to Projects and select again | Local/default project |
| `NOTE_DRAFT_CONFLICT` | Reload the draft and reconcile visible revisions | Silent overwrite |
| `CANDIDATE_EDIT_CONFLICT` | Reload candidate and reapply an intentional correction | Blind retry |
| `SEMANTIC_CONTRACT_UNAVAILABLE` | Inspect readiness and correlated dependency logs | Empty graph/queue or provider switch |
| explicit import abstention | Review the reason and edit manually if desired | Auto-commit or raw Note fallback |

Failed writes must leave no partial semantic mutation. Restart only after
capturing health evidence; a restart is not a substitute for diagnosis.

## Operator commands and safe evidence

```powershell
docker compose ps
docker inspect --format '{{json .State.Health}}' projecta-api-1
docker compose logs --no-color --tail=200 api semantic-core fuseki
.\scripts\run_sprint8_acceptance.ps1
```

Use `.\scripts\run_sprint8_acceptance.ps1 -RunCompose` for the clean-volume
production-image acceptance. It uses a unique Compose project, scans logs for
secret/internal leakage, verifies restart readiness, and removes only its own
volumes unless `-KeepStack` is requested. Use
`.\scripts\run_sprint8_validation.ps1 -RunOntology` for the ontology
container gate. These commands do not authorize production tenant identity or
provider credentials.

Related contracts: [Application API](../architecture/application-api.md),
[Project context selection](../architecture/project-context-selection.md),
[Graph projection API](../architecture/graph-projection-api.md),
[Correlated logging](../architecture/correlated-logging.md), and
[fail-explicit runtime contract](../architecture/fail-explicit-runtime-contract.md).
