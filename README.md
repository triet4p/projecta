# Projecta

Projecta turns project notes into structured, traceable knowledge. Use it to
organize notes, review extracted candidates, explore project relationships,
and ask questions grounded in recorded evidence.

## What you can do

- Work in separate project workspaces without entering or remembering IDs.
- Create structured notes from ordered, typed note items.
- Import note suggestions with AI assistance, then edit them before saving.
- Capture exact source spans into candidates for explicit Review Queue decisions;
  capture itself does not approve or materialize them.
- Review and correct candidates before explicitly confirming or rejecting them.
- Explore a bounded project graph and ask evidence-backed questions.

## Quick start

### Windows 11 x64 unsigned 0.7.0 test pre-release

The owner-authorized 0.7.0 Windows 11 x64 pre-release is one unsigned
installer: `Projecta-Setup-0.7.0-win-x64-unsigned-prerelease.exe`
(119,495,860 bytes; SHA-256
`f7555a90807bff34540a89758e5f8fe5853b8cbd09d3772d40ac4c9d77a64a77`).
Windows cannot verify its publisher, and SmartScreen or antivirus software
may warn or block it. Never disable security controls or bypass a block.

The expected GitHub 0.7.0 asset has not yet been published; no public download
URL is available. Use only the exact owner-approved asset when published,
not a repository or `build`-directory copy. See the
[machine install, start, stop, and uninstall guide](docs/sprint-plans/sprint-14/unsigned-0.7.0-machine-install.md).

Build provenance: package and installer source revision
`674d0cb3e76096a60725556b20be3767e2508e28`; package archive
`ProjectaLocal-0.7.0-win-x64-unsigned-pre-release-test-fixed.zip`
(191,750,058 bytes; SHA-256
`373a4c4aec1ba89f24f68934d4465a7a4be441887c6a21ca327572ac6304bd65`).
The archive is build provenance, not a second installer or download asset.

The installer bundles local services and does not require Docker, Python,
Node.js, or a JDK. It uses the current Windows account's default browser.
This version-specific unsigned exception does not establish clean-Windows
proof, a signed release, or production readiness; signed update verification
remains fail-closed.

### Development quick start (Docker Compose)

For the repository's Docker Compose development workflow, you need Docker Desktop and PowerShell 7 (`pwsh`). From the repository root, copy the local template, generate unique credentials in the ignored `.env`, and start the web profile:

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

1. On the standalone **Projects** chooser, select **Project Alpha** or
   **Project Beta** to enter its workspace.
2. Use **Change project** in the active-project bar to switch; the chooser
   replaces the workspace until another project is selected. Project Overview,
   Notes, Graph, and Review Queue stay within the active project.
3. Open **Notes** and choose **Note Composer** for typed items, **Assisted import**
   for editable proposals from pasted text, or **Capture exact spans** to anchor a
   selected passage to a review candidate. Import proposals require an explicit save;
   draft save and commit remain separate. The server returns the project-scoped
   opaque review handle used by the queue, which selects that exact candidate
   rather than guessing from a label or queue order. A successful capture offers
   **Open Review Queue** and reports a missing candidate instead of selecting a
   different item. Capture does not
   approve or materialize candidates. Returning from an unfinished capture to Notes
   preserves its source and selected spans in memory for **Continue capture** or
   **Discard unsubmitted capture**; changing projects clears that unsaved draft.
4. Open **Graph** directly to explore the project projection, or choose a knowledge
   item in **Project Overview** to open its scoped detail; use **Back to Project
   Overview** to return. Graph nodes spell out verification and lifecycle state,
   outline patterns distinguish node states, and directed edges name their
   relation type. Open **Review Queue** to validate source-bound candidates.
   Project Overview’s **Recent notes** links open the exact Note’s source detail
   in Notes; a missing or unavailable record remains explicit with retry and
   return to Overview.
5. Open **Settings** to configure an OpenAI-compatible provider if you want to
   use assisted import or extraction. Manual composition and exact-span capture
   work without it.
6. Use **Diagnostics** when a service reports an error; request IDs are shown
   so failures can be matched with container logs.

The top bar keeps the session status and **Sign out** available in both the
Projects chooser and workspace screens.

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

If `connector-migrate` exits with PostgreSQL `password authentication failed`
and the database log says `Skipping initialization` or `role ... does not
exist`, the existing Compose volume was initialized with different credentials.
Changing `.env` does not recreate PostgreSQL roles or rotate that volume's
password. Preserve the old data: stop the partial stack **without** `--volumes`
and start a separate project with fresh, empty volumes:

```powershell
docker compose --env-file .env -f compose.yaml -f compose.dev.yaml --profile web down
docker compose -p projecta-fresh --env-file .env -f compose.yaml -f compose.dev.yaml --profile web up -d --build --wait
```

Use the same `-p projecta-fresh` for later `ps`, `logs`, and `down` commands.
The original volumes remain available under the original Compose project, but
their contents do not appear in the fresh project. To reuse that data instead,
recover its original PostgreSQL credentials; do not erase the volume to silence
an authentication error.

For detailed health and recovery guidance, see the
[operations guide](docs/runbooks/sprint-8-operations.md).

## License

Licensed under the [Apache License 2.0](LICENSE).
