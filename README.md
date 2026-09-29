# Projecta

Projecta turns project notes into structured, traceable knowledge. Use it to
organize notes, review extracted candidates, explore project relationships,
and ask questions grounded in recorded evidence.

## What you can do

- Work in separate project workspaces without entering or remembering IDs.
- Create structured notes from ordered, typed note items.
- Import note suggestions with AI assistance, then edit them before saving.
- Review and correct candidates before explicitly confirming or rejecting them.
- Explore a bounded project graph and ask evidence-backed questions.

## Quick start

You need Docker Desktop and PowerShell 7 (`pwsh`) on Windows. From the
repository root, copy the local template, generate unique credentials in the
ignored `.env`, and start the web profile:

```powershell
if (-not (Test-Path -LiteralPath ".env")) {
  Copy-Item -LiteralPath ".env.example" -Destination ".env"
}
pwsh -NoProfile -File ./scripts/setup-local-env.ps1
docker compose --env-file .env -f compose.yaml -f compose.dev.yaml --profile web config --quiet
if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration is invalid." }
docker compose --env-file .env -f compose.yaml -f compose.dev.yaml --profile web up --build
```

The bootstrap command preserves existing non-placeholder credentials, fills
missing values, and refuses a production-mode `.env`; it is safe to rerun.
It does not print credentials. Keep `.env` out of Git, do not share it, and do
not reuse local credentials in production. Docker Compose must run with this
generated `.env`, not the uninitialized `.env.example`. When services are
healthy, open <http://localhost:3000>.

### Optional local suggestions

Manual capture and review work with no model. Leave
`PROJECTA_LOCAL_SUGGESTION_MODEL` empty to keep suggestions disabled. To opt in,
set it in the Git-ignored `.env` to the exact tag of a model already provisioned
for Ollama. Compose forwards this setting only to `api`; its empty default adds no
model or startup dependency.

To exercise suggestions in Docker, provision Ollama separately in the API
container's network namespace and have it listen on `127.0.0.1:11434` there.
Container loopback is not the host loopback, so a host-local Ollama is
inaccessible from the API. Suggestions use only this local Ollama endpoint and
never call or fall back to an external LLM provider. The API never starts
Ollama, probes it during state reads, or pulls/downloads a model. Production
mode unconditionally disables local suggestions.

Use an operator-approved image already available locally and a pre-populated
model store. For example, after setting
`PROJECTA_OLLAMA_IMAGE` to that image reference and
`PROJECTA_OLLAMA_STORE` to the existing store path:

```powershell
$apiContainer = (docker compose --env-file .env -f compose.yaml -f compose.dev.yaml --profile web ps -q api).Trim()
if (-not $apiContainer) { throw "Start the Projecta Compose API first." }
if (-not $env:PROJECTA_OLLAMA_IMAGE -or -not $env:PROJECTA_OLLAMA_STORE) {
  throw "Set PROJECTA_OLLAMA_IMAGE and PROJECTA_OLLAMA_STORE to operator-approved local resources."
}
docker run --detach --pull=never --name projecta-ollama --network "container:$apiContainer" `
  --mount "type=bind,source=$env:PROJECTA_OLLAMA_STORE,target=/root/.ollama" `
  $env:PROJECTA_OLLAMA_IMAGE
docker exec projecta-ollama ollama list
```

Confirm the selected tag is already in that store before setting
`PROJECTA_LOCAL_SUGGESTION_MODEL`. Do not pull a model unless separately
authorized. This sidecar is operator-managed and is not part of Compose startup.

## First steps

1. Select **Project Alpha** or **Project Beta** on the **Projects** page.
2. Open **Notes**, create a note with one or more typed items, then save or
   commit it.
3. Open **Graph** to explore the project and **Review Queue** to validate
   extracted candidates.
4. Open **Settings** to configure an OpenAI-compatible provider if you want to
   use assisted import or extraction. Manual structured notes work without it.
5. Use **Diagnostics** when a service reports an error; request IDs are shown
   so failures can be matched with container logs.

Projecta does not silently choose another project, retry a failed action, or
turn an unavailable result into an empty success. Review the visible error and
retry only after resolving its cause.

## Stop or reset

Stop the app while keeping local data:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile web down
```

To also delete all local Projecta data and start clean, add
`--volumes --remove-orphans`. This cannot be undone.

## Troubleshooting

Check service state and recent logs:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile web ps
docker compose -f compose.yaml -f compose.dev.yaml --profile web logs --tail=200 web api semantic-core fuseki
```

For detailed health and recovery guidance, see the
[operations guide](docs/runbooks/sprint-8-operations.md).

## License

Licensed under the [Apache License 2.0](LICENSE).
