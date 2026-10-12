# Projecta Desktop (Tauri v2 — S15-04 first-run + S15-05 runtime controls + S15-06 trust boundary)

One native Tauri v2 window owns exactly one service tree. On a fresh data
root, it renders the bundled bootstrap surface (`projecta-bootstrap://localhost/`)
and presents an in-window workspace-name form; no service tree starts until a
valid name is submitted. The form invokes the existing `provision` subcommand
with the audited display-name validation, generated project ID,
`local-operator` actor, and DPAPI CurrentUser-protected runtime secrets.
Provisioning is data-only: OS shortcuts and registry installation remain
separate in both frozen and unfrozen execution. Cancel and refused names leave
no workspace state. On success the app starts its owned supervisor; an
existing workspace starts that supervisor directly. In both cases the SAME
window moves to the owned loopback API SPA on real readiness.

Window close is the Stop/Cancel binding: graceful reverse-order stop of owned
children only via the existing `stop` subcommand (prompt owned-child
termination on mid-startup cancel), releasing locks and ports while retaining
data. No Tauri commands, retry loop, Rust process manager, hidden service,
Tkinter, or browser companion. S15-07 external-link adaptation and S15-09
packaging remain later tasks.

## Runtime controls in the same window (S15-05)

The same window presents every contract §2.1 state — `bootstrap`, `starting`,
`ready`, `degraded`, `stopped`, `failed`, `shutdown-failed` — as a bundled
lifecycle surface with two bindings of the existing `start`/`stop` operations:

- a plain form on the lifecycle surface (Start/Stop; no script, no Tauri
  command, no capability change);
- a native `Runtime` window menu (`Start runtime`, `Stop runtime`,
  `Show runtime controls`) so the controls stay reachable after the window has
  navigated to the loopback SPA.

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
  the single-window contract and outside the navigation guard. The explicit
  external-link/system-browser action belongs to S15-07.
- **Native bridge.** No Tauri command is registered and the capability
  manifest is empty, so there is no IPC surface to scope: `withGlobalTauri`
  is explicitly `false`, `window.__TAURI__` is absent, and a direct
  `__TAURI_INTERNALS__.invoke(...)` attempt is refused by the ACL
  (`… not allowed. Permissions associated with this command: …`). All
  supervisor operations stay in the existing local CLI child process.
- **Web permissions.** Sensitive web permissions (geolocation, notifications,
  camera, microphone, clipboard read, and the rest) are denied in every state;
  automatic downloads keep the platform default so S15-07's file-download
  adaptation is not preempted.
- **CSP and web security.** The loopback-only CSP, default same-origin policy,
  and certificate verification are unchanged and never weakened to make
  embedding work.
- **Local API Host/Origin boundary.** The loopback entry point
  (`projecta_api.local_server`) refuses requests whose `Host` header does not
  name a loopback address (DNS-rebinding defense) and any request carrying a
  foreign `Origin` header (local cross-origin forgery defense), with
  `LOOPBACK_BOUNDARY_REJECTED` (403). Embedded/test composition is untouched;
  the guard lives only at the loopback entry point.

## Layout

- `package.json` — npm scripts (`tauri dev` / `tauri build`); pinned
  `@tauri-apps/cli 2.12.2` + `@tauri-apps/api 2.12.3`.
- `src-tauri/Cargo.toml` — pinned `tauri =2.12.3`, `tauri-build =2.7.2`.
- `src-tauri/tauri.conf.json` — no declarative window (the host builds the
  single `main` window in `setup()`), `withGlobalTauri: false`, loopback-only
  CSP, empty capabilities; bundle disabled (S15-09 owns packaging).
- `src-tauri/src/lifecycle.rs` — owned supervisor child, bounded `provision`
  command, readiness polling with manager-exit adoption, lifecycle surface
  renderer (states, controls, sanitized diagnostics), `LifecycleController`
  (cold start / first-run / cancel / user start-stop / adopt / shutdown),
  navigation guard, main-window target and new-window policy, tests.
- `src-tauri/src/` — `main.rs` + `lib.rs`: bootstrap-first host, the single
  boundary-handled main window, same-window first-run form, lifecycle surface
  bindings (bundled form + native Runtime menu), bootstrap⇄SPA transitions,
  and owned-tree shutdown.
- `apps/api/src/projecta_api/loopback_boundary.py` — loopback Host/Origin
  guard wired only into the local loopback entry point
  (`apps/api/src/projecta_api/local_server.py`).

## Disposable lifecycle smoke

Point the native app at a staged package copy, fresh data root, and separate
WebView2 profile. Never use the owner `%LOCALAPPDATA%\Projecta` tree or the
default per-user WebView2 profile:

- `PROJECTA_DESKTOP_PACKAGE_ROOT` → staged package root (bundled
  `runtime/python/python.exe` + `projecta/scripts/projecta_local.py`).
- `PROJECTA_LAUNCHER_DATA_ROOT` → fresh task-owned data root.
- `WEBVIEW2_USER_DATA_FOLDER` → fresh task-owned WebView2 profile.
- `PROJECTA_S15_03_API_PORT` (default `18732`; `PROJECTA_S15_02_API_PORT`
  still honoured as fallback).

Host-validation packages are intentionally rejected by the 0.7.1 runtime
distribution gate. The only permitted local native smoke channel is the exact
`--unsigned-pre-release-test` exception; it remains `releaseEligible=false` and
is not for public distribution. Do not alter the signature gate.

For first-run smoke, launch against a fresh data root without running `install`
or the OS installer. A valid form submission invokes the data-only `provision`
subcommand before the app starts its owned tree; Cancel or invalid input writes
no workspace state. Existing-workspace startup does not reseed. Closing the
window stops only the owned tree; a second launch against the same roots
refuses (`RUNTIME_ALREADY_ACTIVE`) without a second backend/TDB2 writer.
