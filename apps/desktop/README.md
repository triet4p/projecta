# Projecta Desktop (Tauri v2 — S15-04 first-run + S15-03 lifecycle)

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
Tkinter, or browser companion. S15-05 recovery UX, S15-06 trust hardening,
S15-07 external-link adaptation, and S15-09 packaging remain later tasks.

## Layout

- `package.json` — npm scripts (`tauri dev` / `tauri build`); pinned
  `@tauri-apps/cli 2.12.2` + `@tauri-apps/api 2.12.3`.
- `src-tauri/Cargo.toml` — pinned `tauri =2.12.3`, `tauri-build =2.7.2`.
- `src-tauri/tauri.conf.json` — single `main` window on the bootstrap
  surface; loopback-only CSP; bundle disabled (S15-09 owns packaging).
- `src-tauri/src/lifecycle.rs` — owned supervisor child, bounded `provision`
  command, readiness polling, bootstrap renderer, `LifecycleController`
  (cold start / first-run / cancel / shutdown), navigation guard, tests.
- `src-tauri/src/` — `main.rs` + `lib.rs`: bootstrap-first host, same-window
  first-run form and bootstrap→SPA transition on readiness, owned-tree shutdown.

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
