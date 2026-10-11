# S15-01 — Desktop/Runtime Release Contract (Tauri v2, Windows 10/11 x64)

**Status:** `CONTRACT — S15-01 deliverable; implementation authorized for S15-02 only. No release, signing, publication, or clean-host claim is authorized by this document.`

**Scope:** one Tauri v2 main window on Windows 10 + Windows 11 x64 for Projecta 1.0.0, reusing the existing React SPA, the Python supervisor/launcher, Python/FastAPI Application API, PostgreSQL 16, Fuseki/TDB2 6.2.0, and Java 21 Semantic Core behind loopback HTTP ports. Owner selection of Tauri v2 is settled ([decision](../../../.agents/memory/decisions.md#2026-10-10-use-tauri-v2-for-the-single-window-desktop-application)) and is not reopened here.

**How to read this document:** four separated classes of statement.

- **Facts** — observed in current source at base `26ce4a4` (`VERSION` `0.7.1`), cited file-by-file in §16. Facts constrain every rule below.
- **Changed desktop rules** — new normative requirements (`MUST`/`MUST NOT`) for the Tauri cutover. They change the client/lifecycle shell only, never backend semantics.
- **Historical evidence** — prior observations (owner Win10 report, 0.7.x unsigned packages). Informative only; nothing here is fresh proof.
- **Missing prerequisites** — genuinely unknown/blocked items (§14). A missing item blocks its named later gate; it never silently relaxes a rule.

This contract is based on current source and on the three standing contracts: [installation boundary](../sprint-14/installation-boundary-proposal.md), [portable data](../sprint-14/portable-data-contract.md) (`projecta-portable.v1`), and [deletion](../sprint-14/project-data-deletion-contract.md) (`projecta-deletion.v1`). Those contracts are unchanged by this document; where this contract restates one of their rules, the original remains authoritative.

## 1. Baseline facts the contract preserves

The current shippable shape is a per-user native launcher plus loopback services plus a system-browser SPA. The Tauri cutover replaces only the last two links (external browser tab, `webbrowser.open`) with one native window.

| Boundary | Observed current contract | Desktop consequence |
| --- | --- | --- |
| Application API | Python `3.12.10`, FastAPI `0.7.1`, loopback `127.0.0.1:18732` by default (`PORTS["api"]`), stdin-pipe `stop` control (`apps/api/src/projecta_api/local_server.py`). | Tauri calls the same loopback API; no new backend API is introduced. |
| Readiness | `GET /health/live` (liveness) and `GET /health/ready` (200 `{"status":"ready","semanticCore":"ready","oidc":"ready"}`; 503 otherwise) (`apps/api/src/projecta_api/main.py`). | The window's state machine polls the same endpoints; no new readiness semantics. |
| Same-origin SPA | API serves the compiled React build from `PROJECTA_API_WEB_ASSETS_DIRECTORY` at `/`, with 404 guards for `v1`, `health`, `docs`, `redoc`, `openapi.json` and a path-traversal guard (`apps/api/src/projecta_api/main.py`). The web client defaults to an empty base URL with `credentials: "same-origin"` (`apps/web/src/api/client.ts`). | The WebView loads the same loopback origin with the same relative `/v1` and `/health` paths. |
| Service tree | Start order PostgreSQL → Fuseki → Semantic Core → API; stop is the exact reverse (`api`, `semanticCore`, `fuseki`, `postgres`) via control pipe plus `pg_ctl --mode=fast` (`scripts/projecta_local.py`). Ports `15432`/`18303`/`18080`/`18732` are fixed; a collision fails closed with `PORT_IN_USE` and no port is ever chosen automatically. | S15-03 reuses this order, the fixed ports, and the fail-closed collision rule. |
| Single instance | Per-user `state/runtime.lock` (`msvcrt`/`fcntl`); a second start fails with `RUNTIME_ALREADY_ACTIVE`; TDB2 keeps one writer (`scripts/projecta_local.py`). | Exactly one service tree ever; the window layer MUST NOT create a second one. |
| Experience context | Server middleware injects `X-Projecta-Actor-Id` and `X-Projecta-Context-Secret` from launcher-owned settings and the server-side selection store, and strips browser-supplied project/actor/secret/selection headers; production strips them and uses the session cookie (`apps/api/src/projecta_api/context.py`). | The WebView is never given the context secret; trust stays server-established. |
| Connector opt-in | `PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED` defaults to `false`; the launcher inherits an explicitly set process value into the API environment and nothing else (`scripts/projecta_local.py`, `apps/api/src/projecta_api/config.py`). Read-only capabilities apply without it; production rejects it (`apps/api/src/projecta_api/connectors/authorization.py`, `apps/api/src/projecta_api/startup.py`). | The desktop preserves default-false plus explicit opt-in inheritance; it is not WebView authentication. |
| Secrets | DPAPI CurrentUser `secrets/launcher.dpapi`; same-account open only; portable archives MUST NOT carry ciphertext (`scripts/projecta_local.py`, portable/deletion contracts). | Unchanged. The desktop adds no keyring and moves no secret. |
| Data root | `%LOCALAPPDATA%\Projecta`; binaries `%LOCALAPPDATA%\Programs\Projecta\<version>`; HKCU uninstall registration; `RequestExecutionLevel user` (`scripts/projecta_local.py`, `scripts/build_windows_installer.py`, `scripts/projecta-setup.nsi`). | Unchanged paths; §7 lists every file. |
| Updates | User-approved, stopped-runtime, signed-release only: Ed25519 manifest signature, `releaseEligible=true`, `distributionChannel=signed-release`, newer version, matching runtime/data contract (`scripts/projecta_local.py`). | No silent update, no rollback, no downgrade is added. |
| Retry/recovery | Interactive product path is single-attempt; deletion/import recovery is journal-forward completion, never rollback (`docs/architecture/explicit-retry-contract.md`, deletion contract). | The shell adds no retry loop and no repair. |

## 2. Window and lifecycle state transitions

One main application window owns first-run workspace setup, startup/readiness, the existing React journeys, runtime controls, and recoverable error states. Ordinary use MUST NOT require a separate Tkinter panel or system-browser tab. Native OS file/consent dialogs are allowed; external links MAY open the system browser explicitly (§5).

### 2.1 States

The durable states are the launcher status-file states (`starting`, `ready`, `stopped`, `failed`, `shutdown-failed` in `scripts/projecta_local.py`), extended with one desktop-only pre-API state:

- `bootstrap` — the window renders the locally bundled bootstrap surface (§4). No API dependency exists yet; only window chrome plus Start/Stop/diagnostics controls are live.
- `starting` — owned services are being started in order; cancellation is accepted and stops already-started owned children.
- `ready` — all readiness probes pass; the SAME window shows the loopback SPA.
- `degraded` — a previously ready service stopped reporting readiness (`SERVICE_BECAME_UNREADY`); the window shows the failing dependency, a bounded recovery action, and sanitized diagnostics. No automatic restart.
- `stopped` — all owned children exited; locks/ports released; all persistent state retained.
- `failed` — startup or supervision failed with a finite code; owned children stopped; state retained.
- `shutdown-failed` — graceful stop did not complete; the manager waits for an explicit user stop retry; it MUST NOT kill foreign processes or roll back data.

### 2.2 Transitions

```text
bootstrap --(user Start / auto-start)--> starting --(all ready)--> ready
bootstrap --(user Quit)--> stopped
starting --(user Cancel / failure)--> stopped / failed
ready --(probe failure)--> degraded --(user Start recovery, probes pass)--> ready
ready --(user Stop / window Quit)--> stopped
degraded --(user Stop / window Quit)--> stopped
starting|ready|degraded --(fatal supervision error)--> failed --(user Start)--> starting
any --(second launch while lock held)--> refuse-or-activate, no second tree (§3.3)
```

Rules:

- The bootstrap-to-SPA transition happens in the SAME window (same WebView): initial navigation target is the bundled bootstrap asset; on `ready` the window navigates to `http://127.0.0.1:<api-port>/`. No second window, no system-browser handoff.
- Every transition out of `starting`/`ready`/`degraded` stops only owned children in reverse order and releases the lock and ports. Data is always retained.
- `failed` and `degraded` MUST surface the finite failure code (`PORT_IN_USE`, `SERVICE_READINESS_TIMEOUT`, `SERVICE_BECAME_UNREADY`, `PLATFORM_UNSUPPORTED`, `UPDATE_RECOVERY_REQUIRED`, API `reasonCode` values) rather than an empty-success screen.

## 3. Narrow supervisor operations and ownership/close policy

### 3.1 Operations the desktop may invoke

The desktop shell exposes exactly the existing launcher command surface, minus nothing and plus nothing at this contract level:

- `install` — first-run workspace provisioning on a fresh data directory only; never overwrites existing configuration.
- `start` — ordered start with readiness gating; opens no system browser in desktop mode (the window replaces `webbrowser.open`).
- `stop` — graceful reverse-order shutdown request.
- `status` — read-only readiness/state inspection; changes no data.
- `backup create` / `backup restore` — stopped-runtime snapshots only; restore requires explicit confirmation and retains the pre-restore state.
- `update <package>` — user-approved signed package only, stopped-runtime only (§9).

S15-03 binds these to window controls (Start/Stop, bounded recovery, sanitized diagnostics). Any additional native operation the slice needs MUST be named in its task evidence and mapped here by contract amendment — never smuggled in as an unreviewed command.

### 3.2 Operations the desktop MUST NOT add

- No automatic port selection, no port fallback, no LAN binding: every listener stays `127.0.0.1` on its fixed port.
- No automatic retry loop on startup, supervision, readiness, or recovery (single-attempt product rule preserved).
- No rollback, destructive reset, schema downgrade, silent repair, or silent background update.
- No new process manager in Rust: reuse locks, readiness, reverse-order shutdown, and the local CLI.
- No hidden background service, tray service, or global shortcut.
- No killing, suspending, or inspecting processes the manager did not start. The Windows Job Object kill-on-close backstop applies to owned children on abnormal manager exit only.
- No inheritance of foreign secrets into children: the launcher scrubs `PROJECTA_*`, `FUSEKI_*`, `SEMANTIC_CORE_*`, `PG*`, provider-key, proxy, and JVM-option variables before composing the service environment, then sets the exact pinned values (§1). The desktop preserves this scrub-and-set behavior.

### 3.3 Second launch and close policy

- While the per-user lock is held, a second launch MUST NOT start a second PostgreSQL/Fuseki/API tree (TDB2 one-writer rule). It MUST either activate the existing window or refuse with `RUNTIME_ALREADY_ACTIVE`. S15-03 implements one of these; starting Opening a second backend is not an option.
- Window Quit is an ordinary close: request graceful stop, wait for the reverse-order shutdown bounded by the existing timeouts, release lock/ports, retain all data, then exit. Quit MUST NOT delete, reset, or migrate anything.
- Cancellation during `starting` stops owned children started so far (reverse order), releases the lock, retains data, and reports the outcome. Partial customer state from a cancelled first-run provision is forbidden: provisioning writes atomically and refuses to overwrite.

## 4. Workspace versus project boundary

- **Workspace** — one local installation identity: `%LOCALAPPDATA%\Projecta\config\local-runtime.json` (`formatVersion`, `projectId`, `projectName`, `actorId`, optional `projects` registry of at most 100 entries). First-run provisions `My Projecta Workspace` for actor `local-operator` with a slugified project ID, only when the file does not exist. OS shortcut/registry installation is separate from workspace initialization and MUST NOT reseed, overwrite, or resurrect workspace state.
- **Project** — server-owned catalog membership. The visible set is the deployment allowlist (`PROJECTA_API_EXPERIENCE_PROJECT_CATALOG`); selection uses opaque handles (`project-h-<sha256>`) with `catalogRevision`/`selectionRevision` freshness; stale selection fails closed with re-selection, never with client-chosen routing.
- Last-project deletion persists the empty catalog; restart/bootstrap MUST NOT resurrect a seed; fresh create/import stays possible (deletion contract §6).
- The locally bundled bootstrap surface provisions or opens the workspace; it MUST NOT invent project IDs, bypass name validation, expose secrets, or write portable archives.

## 5. Trusted origin and navigation policy

Allowed origins for the privileged main view are exactly:

1. The locally bundled bootstrap asset (package-local, no network fetch).
2. `http://127.0.0.1:<api-port>/` — the loopback API origin serving the compiled SPA same-origin.

Rules:

- The WebView's privileged navigation is restricted to (1) then (2). Any other navigation (third-party URL, foreign loopback port, `file:` URL outside the bundle, custom scheme) MUST be refused in the main view or opened in the system browser only through an explicit user action — never by silently navigating the privileged view.
- Tauri commands and capabilities are scoped to the approved window/origin and to the §3.1 supervisor operations (S15-06 implements the capability manifest; this contract fixes its bounds).
- `PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED`, the context secret, the secret-store master key, PostgreSQL credentials, and provider keys MUST NOT be readable from WebView JavaScript, DOM, URLs, or logs. They travel only in the launcher-composed service environment and server memory, as today.
- The existing server-owned context stays authoritative: browser-supplied project/actor/secret/selection headers are stripped and replaced server-side in `experience` mode; production uses the session cookie. The desktop MUST NOT disable CSP, CORS/SOP, or certificate verification to make embedding work, and MUST NOT change the SPA to a packaged origin without a contract update plus fresh trust/session evidence.
- Cookies remain `same-origin` loopback; CSRF middleware stays enabled; every API response keeps its `X-Request-Id` correlation surface.
- No remote-backend mode: the API base is fixed to the owned loopback origin. No user, file, or build setting may point the desktop at a LAN or hosted backend.

## 6. Preserved opt-in

- `PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED` remains default `false`.
- Inheritance is explicit and narrow: only a value explicitly present in the launcher process environment is forwarded into the API service environment; absence stays `false`. The desktop settings surface MUST NOT silently enable it, persist it behind the user's back, or treat the WebView session as administration.
- Server-selected project/actor authority, production rejection (`CONNECTOR_LOCAL_AUTH_DISABLED_IN_PRODUCTION`, `EXPERIENCE_CONTEXT_DISABLED_IN_PRODUCTION`), redaction of secrets in read responses, and audit behavior are unchanged.
- Connector install/enable/disable/sync/retry remain server-authorized child-API operations reached through the SPA; the desktop adds no native connector API.

## 7. Local data paths

All paths below are per-user. `<data>` is `%LOCALAPPDATA%\Projecta`; `<bin>` is `%LOCALAPPDATA%\Programs\Projecta\<version>`. Mutable state lives outside the install directory so upgrade/uninstall cannot overwrite it.

| Path | Content and owner |
| --- | --- |
| `<bin>\` (package root) | Read-only binaries: launcher/host executable, `runtime\` (Python 3.12.10, Java 21 JRE, PostgreSQL 16.15, Fuseki 6.2.0), `projecta\` (API source, Semantic Core classes, Fuseki config template, ontology, compiled `web\`), `runtime-manifest.json` (+ `.sig` on signed releases), notices/licenses. |
| `<data>\data\postgres\` | PostgreSQL 16 cluster (`PG_VERSION` `16` enforced; version mismatch fails closed). |
| `<data>\data\fuseki\databases\projecta\` | TDB2 dataset; one writer only. |
| `<data>\data\sqlite\operational.db` | Durable app workflow state (schema v1–3). |
| `<data>\data\evidence\` | Immutable SHA-256-checked content objects (JSON/text, 1 MiB cap). |
| `<data>\data\imports\` (+ `previews/<token>/`, `results/`, `ledger.json`) | Portable-import staging, preview bytes, result receipts, import ledger. |
| `<data>\data\exports\` | Exported `.projecta` archives awaiting user download. |
| `<data>\data\deletion\` | Deletion journal state (`journal.json` forward-completion). |
| `<data>\config\local-runtime.json` | Workspace + project registry (workspace boundary, §4). |
| `<data>\config\installation.json` | Installed version/runtime-versions/data-contract record. |
| `<data>\secrets\launcher.dpapi` | DPAPI CurrentUser secrets; same Windows account only. Never copied into portable archives. |
| `<data>\state\runtime.json` | Status document (`starting`/`ready`/`stopped`/`failed`/`shutdown-failed`, services, PIDs). |
| `<data>\state\runtime.lock` | Single-instance lock. |
| `<data>\state\stop.json`, `<data>\state\import-restart.json` | Graceful-stop request; legacy restart marker (recovery-only since S14-17). |
| `<data>\logs\launcher.log` | Sanitized launcher events; no secrets. |
| `<data>\backups\`, `<data>\recovery\` | Stopped-runtime snapshots; import-publication journals. |

Link/junction policy is unchanged: reparse points in data paths fail closed (`LOCAL_PATH_UNSAFE`).

## 8. Supported Windows matrix, prerequisites, and consent

### 8.1 Release scope and support matrix

Owner scope for 1.0.0: **Windows 10 + Windows 11 x64 only**. macOS, Linux desktop packages, ARM64, and older Windows versions are outside this release scope. The Compose developer/server path is preserved unchanged.

| Target | Contract position as of 2026-10-11 |
| --- | --- |
| Windows 10 22H2 x64 | Initial Windows 10 target (owner-selected). Microsoft ended ordinary 22H2 support on 2025-10-14, so Projecta "support" here means tested-target only after S15-16 PASS — no OS security-update promise. Actual Windows 10 compatibility MUST NOT be claimed until S15-16 passes. |
| Windows 11 24H2 x64 (build 26100+) | Supported floor of the Windows 11 matrix: per Microsoft release information, 24H2 Home/Pro is supported through 2026-10-13 and Enterprise/Education through 2027-10-12. |
| Windows 11 25H2 x64 (current annual release) | Supported head of the matrix: per Microsoft release information, 25H2 Home/Pro is supported through 2027-10-12 and Enterprise/Education through 2028-10-10. |
| Windows 11 23H2 and older, Windows 10 older than 22H2, any 32-bit or ARM64 Windows | Out of scope; the runtime MUST refuse them. |

Rules:

- The current guard (`build < 22000` or non-workstation or non-x64 → `PLATFORM_UNSUPPORTED`) stays until S15-08 replaces the floor with the matrix above. S15-08 MUST retain refusal for everything outside the matrix; removing the guard or suppressing the check is forbidden.
- Source-level checks and injected OS values are not compatibility proof. A matrix row is claimed only after its S15-16/S15-17 gate passes on the exact build.
- The exact pinned Tauri version (fixed by S15-02) MUST document a Windows floor at or below this matrix; if the pinned Tauri release drops a matrix row, the matrix shrinks by contract amendment — the implementation MUST NOT ship the row anyway.
- No host access is observed or claimed by this contract task. S15-16/S15-17 MUST record the real OS/build/edition, baseline software/prerequisite inventory, privileges, candidate hash/signature, and measured resources for every claimed row.

### 8.2 WebView2 prerequisite

- The Tauri WebView on Windows requires the WebView2 Evergreen Runtime. An installed Edge browser is NOT proof that the runtime is present; the installer/first-start MUST detect the runtime directly.
- When absent or below the S15-10 floor, the installer offers the official Microsoft bootstrapper under its own terms/consent UI; Projecta MUST NOT mirror, repackage, or silently install it. Decline/failure stops safely with prior binaries/data preserved.
- S15-10 implements detection/consent/verification; S15-16/S15-17 exercise both the present and the missing branches on clean hosts. Post-installation runtime use MUST support the existing no-provider manual journey fully offline.

### 8.3 Visual C++ runtime prerequisite (existing, preserved)

- Minimum: x64 VC v14 `14.42.34438.0`, read from `HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64` (`scripts/projecta_local.py`, `scripts/vc_runtime_prerequisite.ps1`).
- When missing or older, the user is offered the direct Microsoft download (`https://aka.ms/vc14/vc_redist.x64.exe`); the vendor installer keeps its own terms/consent and MAY request UAC. Projecta and its services stay per-user and non-elevated.
- Integrity contract: SHA-256 of the Authenticode-verified download, recomputed and compared immediately before execution; Authenticode remains authoritative. Cancellation, failed verification, failure, or restart-required results MUST NOT start Projecta.
- No MSVC DLLs are bundled and no redistributable installer is shipped (hybrid decision 2026-10-01).

### 8.4 Resource floor

Cold start, whole-process-tree memory, installed/download size, and required disk headroom MUST be measured on the actual tested hosts (S15-16/S15-17) and published as the evidenced support floor. No invented performance target; no claim that Tauri shrinks the backend bundle.

## 9. Signing policy and public artifact naming/inventory

### 9.1 Signing policy (preserved, not relaxed)

- Release channel rule: a releasable package has `releaseEligible=true`, `distributionChannel=signed-release`, an Ed25519 `runtime-manifest.sig` verifiable against the owner release key, a newer version, and matching runtime/data contracts. Anything else is refused (`UPDATE_SIGNATURE_REQUIRED`, `UPDATE_PACKAGE_INVALID`).
- The unsigned 0.7.x exception (`unsigned-pre-release-test`, `releaseEligible=false`, `NotSigned`) does NOT authorize an unsigned 1.0.0. Internal unsigned trials remain explicitly ineligible for public release.
- Signer/certificate identity, timestamping authority, and redistribution permission are unknown and unauthorized as of this contract. S15-12/S15-15 remain blocked on exactly those prerequisites; a missing signer leaves the gate blocked, never signed-by-description. No private keys in repository/artifacts, no signature bypass, no public upload without authorization.

### 9.2 Public artifact naming and inventory

- Installer name pattern: `Projecta-Setup-<semver>.exe` (0.7.1 precedent: `Projecta-Setup-0.7.1.exe`, NSIS 3.13, per-user, HKCU uninstall key, Start Menu `Programs\Projecta\Projecta.lnk`, uninstall retains `<data>`).
- The exact 1.0.0 payload list is owned by S15-09 (package) and sealed by S15-15 (candidate). Every candidate MUST record: file inventory with sizes and SHA-256, source revision plus content-hashed build-input provenance, compiler/runtime inputs, Authenticode/timestamp identity, update-verification identity, payload provenance, required notices/licenses, and version metadata. Tampered or mismatched inputs/signatures refuse release/update (S15-12).
- Version identity stays single-source: `VERSION`, API pyproject/lock/runtime, web package/lock, Semantic Core pom, and launcher `APP_VERSION` MUST agree under `scripts/check_release_contract.py` (currently all `0.7.1`).

## 10. Desktop action map (acceptance core)

Every desktop user action maps to a real existing operation or to the named later S15 task that implements it. No action maps to "to be decided".

| Desktop action | Existing operation or named later task |
| --- | --- |
| Install for current user | `install` (`scripts/projecta_local.py`); S15-10 NSIS flow; S15-11 upgrade preservation |
| First-run workspace create | `provision_first_run_workspace` (fresh directory only); S15-04 in-window provisioning |
| Start runtime, reach readiness | `RuntimeManager.start`, `GET /health/ready`; S15-03 lifecycle, S15-05 states |
| Open app / use current journeys | Loopback SPA in the same window; S15-02 host, S15-13 parity |
| Select project, switch workspace screen | `POST /v1/projects/selection`, catalog/overview reads; existing React navigation (unchanged) |
| Notes capture, exact-span review, receipts | Existing `/v1/quick-notes`, candidates, review, history routes; S15-13 packaged-window proof |
| Graph, Knowledge, Q&A reads | Existing projection/knowledge/answer routes; no new semantic API |
| Settings: LLM profile read/write/rotate/remove/test | Existing `/v1/settings/llm*` operations; secrets stay server-side |
| Connections: view, install/configure, enable/disable, sync/retry | Existing connector routes under the preserved opt-in (§6); no new connector |
| Export project archive | Existing export operation (`EXPORT_*` finite errors); S15-07 file-download adaptation |
| Import project archive (preview/apply/cancel) | Existing import operations (`IMPORT_*` finite errors, journal-forward recovery); S15-07 file-picker adaptation |
| Delete project (typed confirmation) | Existing deletion operations (`DELETE_*` finite errors, journal-forward completion); no undo |
| Backup create / restore with confirmation | Existing `BackupManager` (stopped-runtime); no auto-backup on delete |
| Apply signed update | Existing `apply_update` (signed-release, stopped-runtime); no silent update |
| Stop runtime / Quit app | `stop` graceful reverse-order shutdown (§3.3); S15-03 ownership |
| View diagnostics after failure | `status`, `state/runtime.json`, `logs/launcher.log` codes; S15-05 presentation |
| Follow an external link | System browser via explicit action only (§5); S15-07 adaptation |
| Cancel a file choice | Safe cancel with zero state change; S15-07 proof |
| Second launch while running | Refuse-or-activate, never a second tree (§3.3); S15-03 |
| Run on an unsupported OS/arch | `PLATFORM_UNSUPPORTED` refusal; S15-08 new floor |

Out of scope for every action above: remote backends, new semantic APIs, credential exposure, autoretry, rollback, silent update, and UX redesign.

## 11. 0.7.1 upgrade and data obligations

- Upgrade replaces the launcher/install payload without resetting the workspace: data roots, all stores (PostgreSQL, TDB2, SQLite, evidence), DPAPI ownership (same Windows account), project catalog/empty-catalog state, evidence/provenance/receipts, optional provider configuration, and backup/update safeguards are retained.
- Only genuinely changed install/config metadata is migrated; no new portable format, no schema downgrade, no destructive repair. A runtime/data-contract change requires a reviewed migration (`UPDATE_RECOVERY_REQUIRED`); an interrupted or refused upgrade follows the existing recovery contract without mixed state.
- Ordinary uninstall removes binaries and per-user registration and retains `<data>`. DPAPI secrets unreachable under another account follow the existing reconfiguration rule (re-provision, never transplant).
- A disposable 0.7.1 fixture upgrading to the candidate and surviving app restart is proved by S15-11; frozen-installer proof is required again by S15-18. This contract promises the obligations, not the proof.

## 12. What the desktop MUST NOT introduce

- No remote-backend mode, no LAN exposure, no new semantic API, no direct React-to-PostgreSQL/Fuseki/Semantic-Core calls (typed Application API only).
- No credential exposure: no secret in WebView JS, DOM, URL, logs, portable archives, or error text.
- No autoretry, no rollback, no silent update, no new updater service.
- No new UX scope: existing screens, routes, context, and project isolation stay; S15-04/05/07 adapt hosting behavior only.
- No OIDC-for-local invention, no native keyring replacement, no tray/global shortcuts, no cloud hosting or synchronization, no new connectors, no model/provider evaluation, no ontology change.
- No second competing installer, no developer-toolchain requirement (no user-installed Docker, Python, Java, Node, PostgreSQL, Rust, or C++ tools), no compatibility launcher shim, no auto-browser app path.
- No weakening of production guards, approval gates, evaluation/materialization locks, or the signed release/update policy.

## 13. Historical evidence (informative, not proof)

- Owner report: a 0.7.1 setup step succeeded on a Windows 10 machine, but workspace creation was refused by the then Windows 11-only platform guard (`_require_windows_11_x64`, `PLATFORM_UNSUPPORTED`). Accepted as ground truth about that old build; it proves neither Windows 10 runtime compatibility nor anything about the Tauri candidate. Windows 10 support is deferred to S15-08/S15-16, not inferred.
- The 0.7.x line shipped unsigned test packages only (`releaseEligible=false`, Authenticode `NotSigned`, Ed25519 absent), with hash-verified payload inventories and developer-host readiness runs. Those runs are not clean-host, signing, or missing-prerequisite proof; the corresponding 1.0.0 gates stay open.
- Sprint 14 completion (tag `v0.7.1`, source `26ce4a4`) is the published baseline for upgrade fixtures, not the assumed base of any future worker attempt.

## 14. Genuinely missing prerequisites (blocked vs runnable)

Blocked until supplied (each blocks only its named gate):

- Public signer identity, certificate/timestamp path, and redistribution permission — blocks S15-12/S15-15/S15-21 release claims. The policy (§9.1) is settled; the credentials are not.
- Authorized disposable/resettable standard-user validation hosts for Windows 10 22H2 x64 and Windows 11 24H2/25H2 x64, with and without WebView2/VC prerequisites — blocks S15-16/S15-17. No host is claimed here.
- Exact pinned Tauri version and its documented Windows/WebView2 floor — produced by S15-02, checked against §8.1.
- Owner acceptance of the frozen candidate on a new host — S15-20; agent runs cannot supply it.

Runnable now under this contract:

- S15-02 live vertical slice on the development host with disposable roots/ports: Tauri window → bootstrap → same-window loopback SPA → project/Notes journey → close without touching externally owned services. Browser-only runs remain regression-only, never native-window proof.

## 15. Sufficiency for S15-02 (what the slice may assume and must prove)

S15-02 MAY assume: the fixed loopback origin and ports, the served-SPA path, the server-owned context and opt-in rules, the data paths, the state transitions and close policy, and the prerequisite/signing policies above. S15-02 MUST prove: real Tauri/WebView launch against a disposable live backend, in-window navigation of a current project/Notes journey, and clean close with no Tkinter/browser companion and no mutation of externally owned services. S15-02 MUST NOT: change the OS floor, add supervisor operations, widen origins/capabilities, bundle new runtimes, or claim any matrix row.

## 16. Sources

Current-source facts (§1–§7, §§9–11):

- `scripts/projecta_local.py` — `APP_VERSION`/`RUNTIME_VERSIONS`/`VC_RUNTIME_PREREQUISITE`/`PORTS`/timeouts; `ProjectaPaths` layout and `%LOCALAPPDATA%` discovery; `_require_windows_11_x64`; `RuntimeManager.start`/ordered start/reverse-order stop/`_supervise`/`_stop_owned_processes`; lock/`RUNTIME_ALREADY_ACTIVE`; fixed-port `PORT_IN_USE`; workspace provisioning and registry rules; DPAPI CurrentUser boundary; `_clear_inherited_secrets` plus `_api_environment` opt-in inheritance; `install`/`apply_update` (signed-release, stopped-runtime, version/contract gates); `BackupManager`; status states and `_open_browser` (replaced by the Tauri window).
- `apps/api/src/projecta_api/local_server.py` — loopback host/port and stdin-pipe `stop`.
- `apps/api/src/projecta_api/main.py` — `/health/live`, `/health/ready` (ready/not-ready shapes), same-origin SPA serving with API-path and traversal guards, typed router composition.
- `apps/api/src/projecta_api/routes.py` plus `connectors/public_api.py` and `identity/routes.py` — the §10 operation inventory (projects/selection/overview, notes/candidates/review/history, graph/knowledge/Q&A, settings LLM profiles, connectors, portable export/import, deletion, auth session).
- `apps/api/src/projecta_api/context.py` — server-established experience context and header stripping.
- `apps/api/src/projecta_api/config.py`, `startup.py` — `experience` mode, `web_assets_directory`, default-false opt-in, production rejection, fail-closed startup problems.
- `apps/api/src/projecta_api/connectors/authorization.py` — read-only default vs explicit admin capabilities.
- `apps/web/src/api/client.ts`, `apps/web/src/shell/App.tsx`, `apps/web/src/shell/AuthShell.tsx`, `apps/web/src/shell/navigation.ts` — empty-base-URL same-origin client with `same-origin` credentials and CSRF/request correlation; unchanged screen/navigation/consent shell.
- `scripts/build_native_package.py`, `scripts/build_windows_installer.py` (pinned NSIS 3.13 + archive SHA-256, per-user receipt fields), `scripts/projecta-setup.nsi` (`RequestExecutionLevel user`, HKCU uninstall key), `scripts/vc_runtime_prerequisite.ps1` (x64 registry check), `scripts/check_release_contract.py` (single-version rule; all components `0.7.1`), `VERSION`, `CHANGELOG.md`.

Standing contracts and records:

- [Installation boundary](../sprint-14/installation-boundary-proposal.md), [portable data](../sprint-14/portable-data-contract.md), [deletion](../sprint-14/project-data-deletion-contract.md); [Sprint 15 plan](../sprint-15.md); [deployment choice](../../initialization/08-Deployment-Choice.md); [runtime configuration](../../architecture/runtime-configuration.md); [explicit retry](../../architecture/explicit-retry-contract.md); [secret manager](../../architecture/secret-manager-contract.md); decisions in `.agents/memory/decisions.md` (2026-09-30 launcher route, 2026-10-01 VC hybrid, 2026-10-02 provenance/checkpoint delegation, 2026-10-08 live publication and journal-forward deletion recovery, 2026-10-10 Tauri v2 selection).

Vendor information checked 2026-10-11:

- Microsoft lifecycle: Windows 10 22H2 ordinary end of support 2025-10-14; Windows 11 23H2 Home/Pro end 2025-11-12 (Enterprise/Education 2026-11-10); 24H2 Home/Pro through 2026-10-13 (Enterprise/Education 2027-10-12); 25H2 Home/Pro through 2027-10-12 (Enterprise/Education 2028-10-10) ([release information](https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information), [end-of-support announcement](https://learn.microsoft.com/en-us/lifecycle/announcements/windows-10-end-of-support)).
- Tauri v2 prerequisites: Windows 10 1803+ and Windows 11 carry WebView2; the exact floor follows the S15-02 pinned Tauri release ([prerequisites](https://v2.tauri.app/start/prerequisites/), [WebView versions](https://v2.tauri.app/reference/webview-versions/)).
