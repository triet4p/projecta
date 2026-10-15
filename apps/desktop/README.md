# Projecta Desktop (Tauri v2 — S15-07 UX revision: workspace management, auto-start, real progress)

One native Tauri v2 window owns exactly one service tree and exactly two
top-level surfaces: the bundled **workspace-management** surface and the
existing loopback SPA (**active workspace**).

Opening the app on an existing workspace starts its owned runtime once, by
itself: there is no Start screen and no required Start click. While it starts,
the same window shows the eight real initialization steps — application
package, owned supervisor process, PostgreSQL `:15432`, Fuseki `:18303`,
Semantic Core `:18080`, API `:18732`, core readiness, session readiness — each
with the status this process actually observed (fixed-port liveness and the
API's own `/health/ready` fields). No timer, no percentage, no invented
success. On real readiness the same window navigates to the owned loopback SPA.

While the startup is in flight, a distinct **startup overlay** covers the
workspace-management shell: a fixed, non-modal layer of the same
server-rendered document (same design tokens, light/dark, no script) with a
loading indicator, the same real step model, and the existing bounded
`Cancel startup` binding; a screen reader or keyboard user is never trapped,
and the shell below is `inert` so focus cannot land on covered controls. The
overlay is dismissed by evidence, not by a timer: real readiness (the window
navigates on to the SPA) or any terminal outcome (the shell with its failure
banner, diagnostics, and recovery controls becomes reachable again — nothing
is covered while the user needs to act). The page's own 2-second refresh keeps
the overlay truthful.

A data root with no workspace shows the same surface with an inline
create-workspace card (no separate wizard screen). Submitting a valid name
accepts the request synchronously and runs the packaged frozen
`ProjectaLocal.exe provision` command on an owned worker, so the window
immediately renders the creating overlay instead of blocking on the request;
validation still runs in the host first, so a refused or invalid name writes
nothing and spawns nothing. The audited display-name validation, generated
project ID, `local-operator` actor, and DPAPI CurrentUser-protected runtime
secrets are unchanged. Creation is data-only: OS shortcuts and registry
installation remain separate. Both workspace provisioning and runtime start
use the already-packaged frozen supervisor because the signed-release
verification anchor is embedded there; the Tauri host invokes that existing
sidecar rather than the source Python module. Cancel and refused names leave no
state, and a create in flight is cancelled as an app-owned child if the window
closes — the close path also joins the create worker, so no worker (and no
child it could still spawn) outlives the window.

Window close is the Stop/Cancel binding at every stage: an in-flight create
child is stopped, an in-flight startup is cancelled, and the owned supervisor
is stopped through the manager's existing runtimeId-matched `state/stop.json`
protocol (reverse order, locks/ports released, data retained). No Tauri
commands, retry loop, Rust process manager, hidden service, Tkinter, or browser
companion. S15-09 packages this host as `Projecta.exe` next to the bundled
runtime payload; `start` never opens a browser in any mode.

The same protocol is reachable from the launcher CLI: `stop` writes the request
for the runtime named by the shared status, and `stop --runtime-id <id>` binds
that request to one exact runtime identity — when the active runtime is a
different one, the command refuses with `PROCESS_OWNERSHIP_CONFLICT` and writes
no stop file, so a stale or foreign ID can never stop another owned runtime.
The no-argument form keeps its existing behavior.

On Windows, the host places the exact supervisor child in a kill-on-close
Job Object using the extended-limit information required for
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. If job creation, configuration, or
assignment fails, startup stops and reaps only that just-created child, and
the existing finite `SUPERVISOR_SPAWN_FAILED` result is surfaced; the host
never starts uncontained. This is a close/crash tree-cleanup backstop, not a
replacement for graceful shutdown through the manager's existing `stop`
protocol.

For a frozen one-file supervisor, the manager can be the bootloader's direct
worker; it is adopted only while active, in this launch's Job Object, directly
parented to the launched bootloader, and resolving to the packaged
`ProjectaLocal.exe` image. The runtime ID must be fresh, and ready status plus
API readiness must still match that exact identity. An unrelated same-image
process or other job descendant never establishes ownership.

## Browser-dependent interactions in the same window (S15-07)

The loopback SPA keeps its existing React/typed-API surface; the host adapts
only the WebView-side behavior of five browser-dependent interactions. No new
native data API, project route, or screen was introduced, and project
list/selection/import/export still run through the existing API.

- **File selection (import).** The manual-transfer file input is the usual
  `<input type="file" accept=".projecta">`; the platform shows its own Open
  dialog. Cancelling the dialog (Escape) leaves zero state change: no selected
  file, no staged preview, and no API call. Choosing a file stages the preview
  and the apply step through the existing `/v1/imports/...` routes only.
- **Portable archive download (export).** The export button produces a
  same-origin blob download of the server-built `.projecta` archive. The host
  owns the download destination: a normal run keeps the platform's own
  download folder (exactly the previous system-browser behavior), while an
  absolute `PROJECTA_DESKTOP_DOWNLOAD_DIR` — a disposable proof root, the same
  mechanism as the other disposable roots this host already honours — writes
  the archive there instead. The requested file name is always preserved; the
  download never navigates the privileged view, and no capability is added
  (`AutomaticDownloads` keeps the platform default).
- **Clipboard.** The SPA performs no clipboard API call. Keyboard copy/paste
  inside the SPA fields uses the ordinary operating-system clipboard, and the
  clipboard-read web permission stays denied from the WebView, so a page can
  never read the clipboard without a gesture.
- **Keyboard/navigation.** Tab order, Enter/Space activation, same-document
  hash links (`#note-composer`), and reload (F5/Ctrl+R) behave as in the
  browser SPA and stay on the owned loopback origin; the server-owned
  selection survives a reload. The navigation guard still refuses any
  privileged navigation to third-party content, foreign loopback ports,
  `file:` URLs, and other custom schemes.
- **Allowed external links.** A link that would open a new window
  (`window.open`, `target="_blank"`) is an explicit hand-off, never a render:
  absolute `http`/`https` destinations are opened in the user's system browser
  (the desktop replacement for `webbrowser.open`, via the shell's `open`
  verb), the privileged view is never navigated there, and every non-web
  scheme (`file:`, `data:`, `javascript:`, app custom schemes) is refused with
  no hand-off. No second application window is ever created.

## Workspace management and runtime controls in the same window (S15-05 reworked by S15-07 UX)

The same window presents every contract §2.1 state — `bootstrap`, `starting`,
`ready`, `degraded`, `stopped`, `failed`, `shutdown-failed` — on ONE
management surface that is the only binding of the existing `start`/`stop`
operations:

- a plain form on the surface (Start/Retry startup, Stop/Cancel startup, Open
  project workspace; no script, no Tauri command, no capability change).

The host registers **no native menu bar** and no tray service or global
shortcut: the window keeps only its OS title bar with the standard
minimize/maximize/close controls. The S15-05 `Runtime` menu was removed in the
S15-07 UI revision because the owner reported its single-item bar as a
redundant strip. The round trip it used to provide is preserved without it: on
the ready SPA the window's own header carries one desktop-only `Manage
workspace` action that navigates the same window back to this management
surface, and `Open project workspace` returns to the same SPA — neither
direction stops, restarts, or reseeds the owned runtime, and the surface is
still reached by itself on first view and after a post-ready failure. The
action is rendered only inside the desktop window's own WebView (that WebView
is the only place `window.isTauri` exists), so a browser-served SPA shows no
dead control; it uses the same bundled surface origin as every other surface
navigation, so no command, capability, origin, or window rule changed. The
control lives in `apps/web/src/shell/desktop-shell.ts` + `App.tsx`. Closing
the window remains the way to stop the owned tree.

The surface itself is read-only about the machine: it renders the validated
workspace record (`projectName`, `projectId` — never the data-root path), the
eight observed initialization steps in the supervisor's own start order, and
the finite failure record. A step is `Done` only from a real observation on
this machine (the fixed port answered, or `/health/ready` reports that
dependency `ready`); `Active` is the first not-yet-observed step; `Failed` is
the step the finite failure record blames.

Recovery is bounded and user-initiated only: Start is refused while
starting/ready, Stop cancels a `starting` tree, and a `degraded` runtime
(after-ready service failure) offers exactly one Start attempt. Diagnostics are
sanitized by construction: the state word, the supervisor's finite failure code
(`PORT_IN_USE`, `SERVICE_BECAME_UNREADY`, `GRACEFUL_STOP_TIMEOUT`, …), the
failing service name, and for `PORT_IN_USE` which fixed loopback port is
occupied — all read from the owned `state/runtime.json` document the existing
`status` command reads, or from the owned child's stderr tail. No secret, log
line, path, or raw service output is rendered, and nothing retries
automatically. While the manager reports `shutdown-failed` it stays alive
awaiting the explicit stop retry; the surface Stop writes that retry request
instead of terminating the manager.

The startup overlay exists only while the real `starting` window can still
change by itself, in two honest modes: **creating** (an accepted create request
whose owned `provision` child is writing the workspace record — no service
step is claimed, because none has started) and **starting** (the owned runtime
services coming up — the same eight observed steps as the shell, with the live
count). It carries no timer and no percentage, it is not a dialog, it never
takes focus, and the shell behind it is `inert`. On a first-run failure the
overlay is gone and the management surface states the finite code and points
back at the create form for one new bounded attempt (a stopped creation leaves
a complete record or none); on any other failure it states the supervised
failure and offers the same bounded recovery as before.

Creation interruption boundary: `provision` validates the name before any
write and then writes each artifact atomically (`atomic_write`: temp file +
`fsync` + `os.replace`), refusing to overwrite an existing record. A cancelled
creation therefore leaves a complete record or no record — never a partial or
invalid one — and the next launch reads exactly what is there. The desktop
deletes nothing and never recreates a record it did not create on a fresh data
root; an unreadable record is stated with its finite code and offers no create
form. The create request runs on an owned worker so the window stays
responsive; the close path cancels the owned child and joins that worker, and
a cancel requested before the worker spawns is refused before any writer
exists.

Local session chrome: the SPA omits `Signed in`/`Sign out` only when
`/v1/auth/session` reports `identity: "server-owned-experience"`. That is the
local runtime's own server-side context (no identity provider, `POST
/auth/logout` revokes nothing, the reload re-enters the same context), so the
control is chrome that cannot do what it says. Browser and production sessions
keep both controls, and no API authorization, header injection, CSRF, CSP, or
Origin rule changed.

## WebView/native trust boundary (S15-06)

The privileged main window is the only trusted surface, and its boundary is
explicit rather than inherited from defaults:

- **Window creation.** The single `main` window is built in `setup()` from the
  exact former declarative configuration (title `Projecta`, 1280x860, minimum
  1024x640, resizable, centered, initially the bundled bootstrap surface) so
  its WebView-level handlers are part of the reviewed host source instead of
  window configuration. `tauri.conf.json` declares no window.
- **Navigation.** The `on_navigation` guard admits exactly the bundled
  bootstrap surface (`projecta-bootstrap://localhost/`, plus WebView2's exact
  workaround origin `http://projecta-bootstrap.localhost/` on default port 80
  without credentials) and the owned loopback API origin
  `http://127.0.0.1:<port>/`. Every other target — third-party origins,
  foreign loopback ports, `file:` URLs, other custom schemes, lookalike or
  credential-bearing workaround hosts — is refused in that view.
- **Secondary windows.** `window.open` and every other new-window request is
  denied in the privileged view; a second window would render content outside
  the single-window contract and outside the navigation guard. An allowed
  external link is handed to the system browser instead (S15-07).
- **Native bridge.** No Tauri command is registered and the capability
  manifest is empty, so there is no IPC surface to scope: `withGlobalTauri`
  is explicitly `false`, `window.__TAURI__` is absent, and a direct
  `__TAURI_INTERNALS__.invoke(...)` attempt is refused by the ACL
  (`… not allowed. Permissions associated with this command: …`). All
  supervisor operations stay in the existing local CLI child process.
- **Web permissions.** Sensitive web permissions (geolocation, notifications,
  camera, microphone, clipboard read, and the rest) are denied in every state;
  automatic downloads keep the platform default so the portable-export
  download works without a capability.
- **CSP and web security.** The loopback-only CSP, default same-origin policy,
  and certificate verification are unchanged and never weakened to make
  embedding work.
- **Local API Host/Origin boundary.** The loopback entry point
  (`projecta_api.local_server`) refuses requests whose `Host` header does not
  name a loopback address (DNS-rebinding defense) and any request carrying a
  foreign `Origin` header (local cross-origin forgery defense), with
  `LOOPBACK_BOUNDARY_REJECTED` (403). Embedded/test composition is untouched;
  the guard lives only at the loopback entry point.

## Supported Windows matrix (S15-08) and prerequisites (S15-10)

The owned supervisor accepts Windows 10 22H2 (build 19045) and Windows 11 24H2
and newer (build 26100+) on x64 workstations only, per the S15-01 contract §8.1.
`_require_supported_windows_x64` in `projecta/scripts/projecta_local.py` is the
single guard, applied by `start`, `provision`, `install`, and `apply_update`
before any state is written; every other OS, build, Windows Server product type,
32-bit process, or ARM64 host (including an x64 process emulated on ARM64,
detected with `IsWow64Process2`) gets the finite `PLATFORM_UNSUPPORTED` refusal.
The guard is never suppressed, and no matrix row is claimed as supported until
its S15-16/S15-17 gate passes on the exact build.

Before the window starts, `ProjectaStart.ps1` enforces both vendor
prerequisites in order — WebView2 Evergreen runtime first (the window cannot
render without it), Visual C++ v14 x64 second (the bundled backend cannot start
without it). WebView2 is detected directly at its runtime GUID under the
EdgeUpdate Clients key (never the Edge browser key, never ClientState); when
missing or below Evergreen `109.0.1518.78`, the official Microsoft bootstrapper
is offered with its own consent UI and signature/integrity verification, and
any decline/failure/restart-required outcome stops safely with prior binaries
and data retained. Only a disclosed vendor installer may elevate; Projecta and
its services stay per-user and non-elevated.

## Layout

- `package.json` — npm scripts (`tauri dev` / `tauri build`); pinned
  `@tauri-apps/cli 2.12.2` + `@tauri-apps/api 2.12.3`.
- `src-tauri/Cargo.toml` — pinned `tauri =2.12.3`, `tauri-build =2.7.2`.
- `src-tauri/tauri.conf.json` — no declarative window (the host builds the
  single `main` window in `setup()`), `withGlobalTauri: false`, loopback-only
  CSP, empty capabilities; bundle disabled (S15-09 owns packaging). `bundle.icon`
  names the two generated icon files below so the executable resource and the
  window icon come from one source.
- `src-tauri/icons/icon.ico` — the Projecta application mark for Windows: one
  seven-size ICO (16/24/32/48/64/128/256) built with uncompressed 32bpp DIB
  frames, which `tauri-build`/`rc.exe` embeds as the executable's icon resource
  (Explorer, taskbar, Alt-Tab) and which Tauri then loads as the window icon
  (`icons/icon.png` is the 256px fallback used by non-Windows targets). Both are
  generated from the single 1024×1024 designer master
  (`artifacts/sprint-15/handoffs/S15-07-UX-D2-assets/mark-1024.png`); there is no
  runtime icon code and the placeholder art is replaced in place.
- `src-tauri/src/lifecycle.rs` — starts and provisions through the packaged
  frozen `ProjectaLocal.exe` with exact `%LOCALAPPDATA%/Projecta` routing;
  owns supervisor and creation children, bounded `provision` command,
  real initialization-step model (`build_init_steps`), workspace-management
  renderer (states, controls, sanitized diagnostics), `LifecycleController`
  (cold start / create / cancel / user start-stop / adopt / shutdown /
  `management_view`), navigation guard, main-window target and new-window
  policy, external-link and download-destination policy (S15-07), tests.
- `src-tauri/src/` — `main.rs` + `lib.rs`: bootstrap-first host, the single
  boundary-handled main window (navigation guard, secondary-window refusal,
  external-link system-browser hand-off, owned download destination, denied
  sensitive web permissions), same-window management-surface bindings
  (create/start/stop/open), bootstrap⇄SPA transitions, and owned-tree shutdown.
- `apps/api/src/projecta_api/loopback_boundary.py` — loopback Host/Origin
  guard wired only into the local loopback entry point
  (`apps/api/src/projecta_api/local_server.py`).

## Disposable lifecycle smoke

Point the native app at a staged package copy, fresh data root, and separate
WebView2 profile. Never use the owner `%LOCALAPPDATA%\Projecta` tree or the
default per-user WebView2 profile:

- `PROJECTA_DESKTOP_PACKAGE_ROOT` → staged package root containing the frozen
  `ProjectaLocal.exe` supervisor.
- `PROJECTA_LAUNCHER_DATA_ROOT` → task-owned `<LOCALAPPDATA>/Projecta` data
  root. Set the Tauri host's `LOCALAPPDATA` to the unique task-owned parent;
  the frozen child ignores the launcher-data override and derives this exact
  root from `LOCALAPPDATA`, so never use an ambient default or the ignored
  override alone for isolation.
- `WEBVIEW2_USER_DATA_FOLDER` → fresh task-owned WebView2 profile.
- `PROJECTA_S15_03_API_PORT` (default `18732`; `PROJECTA_S15_02_API_PORT`
  still honoured as fallback).
- `PROJECTA_DESKTOP_DOWNLOAD_DIR` → optional absolute directory for the
  portable-export download. Unset keeps the platform's own download folder
  (normal product behavior); set it to a task-owned disposable root so a
  proof run never writes into the owner's Downloads folder.

Host-validation packages are intentionally rejected by the runtime
distribution gate. Local native smoke uses either the exact
`--unsigned-pre-release-test` exception (`releaseEligible=false`, not for
public distribution) or an owner Ed25519-signed release package. A signed
release without configured Authenticode is truthfully `NotSigned`: Windows
cannot verify the publisher and SmartScreen may warn; the Ed25519 update
signature still verifies. Do not alter the signature gate.

For smoke on a fresh workspace, launch against a fresh data root without
running `install` or the OS installer: the management surface shows the inline
create card and no service tree is started. A valid submission invokes the
data-only `provision` subcommand and then starts the owned tree; Cancel,
invalid input, or closing the window during creation writes no workspace state
that this app did not ask the launcher to write. Existing-workspace startup
does not reseed and needs no Start click: opening the app is the start action.
Closing the window stops only the owned tree — including a creation still in
flight — and a second launch against the same roots refuses
(`RUNTIME_ALREADY_ACTIVE`) without a second backend/TDB2 writer.
