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

### Windows 10 and Windows 11 x64 desktop application

Projecta 1.0.0 is one per-user Tauri v2 desktop application window on Windows 10
and Windows 11 x64. It bundles its own local services and native runtimes, so it
does not require Docker, Python, Node.js, a JDK, PostgreSQL, or Fuseki installed
separately. The single main window is the only client; the desktop product never
opens a system-browser app path.

Supported targets (targeted support, not yet clean-host proven):

- Windows 10 22H2 x64 (build 19045).
- Windows 11 24H2 x64 (build 26100) and Windows 11 25H2 x64.
- Windows 11 23H2 and older, Windows 10 older than 22H2, any 32-bit Windows, and
  ARM64 are refused with `PLATFORM_UNSUPPORTED`.

Install and upgrade:

- Install `Projecta-Setup-1.0.0.exe` for the current Windows user. Setup is
  per-user and is never elevated; it installs to
  `%LOCALAPPDATA%\Programs\Projecta\1.0.0`, and mutable state stays in
  `%LOCALAPPDATA%\Projecta`.
- If the WebView2 Evergreen runtime or the x64 Visual C++ prerequisite is
  missing, setup offers the official Microsoft installer under that installer's
  own license and consent UI, and a Windows UAC prompt may appear for it alone.
- Upgrading from a published 0.7.1 installation replaces the application payload
  and keeps the workspace, stores, evidence, review receipts, and same-account
  secret access. An ordinary uninstall removes the application and retains
  `%LOCALAPPDATA%\Projecta`.
- Updates are user-approved, stopped-runtime, and verified against the owner's
  Ed25519 release signature. There is no silent update and no rollback.

Release status and limits:

- No 1.0.0 tag, release, or public asset exists yet: this repository state seals
  the release source identity. Do not run a checkout or use a file from the
  repository `build` directory as a release.
- This release is not Authenticode-signed; publisher signing is optional and
  unconfigured. Windows cannot verify the publisher, and SmartScreen or
  antivirus software may warn. Never disable security controls or override a
  Defender alert, hard block, or organization policy.
- The Windows targets above are a tested-target commitment, not clean-host
  proof: fresh installs on the target operating systems, including the
  missing-prerequisite branch and the measured resource floor, and owner
  acceptance on a new host remain open in the
  [current Sprint 15 plan](docs/sprint-plans/sprint-15.md).

Historical 0.7.x records, including the unsigned 0.7.0 and 0.7.1 installers and
their disclosed limits, remain in [CHANGELOG.md](CHANGELOG.md) and the
[Sprint 14 plan](docs/sprint-plans/sprint-14.md).

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
