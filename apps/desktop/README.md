# Projecta Desktop (Tauri v2 — S15-03 lifecycle)

One native Tauri v2 window owning exactly one service tree. App launch is the
Start binding: the app spawns the existing local CLI
(`projecta/scripts/projecta_local.py start --no-browser`) as its owned
supervisor child, renders the locally bundled bootstrap surface
(`projecta-bootstrap://localhost/`) first, then navigates the SAME window to
the owned loopback Application API SPA on real readiness. Window close is the
Stop/Cancel binding: graceful reverse-order stop of owned children only via
the existing `stop` subcommand (prompt owned-child termination on mid-startup
cancel), locks/ports released, data retained. No Tauri commands, no retry
loop, no Rust process manager, no hidden service. First-run (S15-04),
states/recovery UX (S15-05), trust hardening (S15-06), file/external-link
adaptation (S15-07), and packaging (S15-09) remain later tasks.

## Layout

- `package.json` — npm scripts (`tauri dev` / `tauri build`); pinned
  `@tauri-apps/cli 2.12.2` + `@tauri-apps/api 2.12.3`.
- `src-tauri/Cargo.toml` — pinned `tauri =2.12.3`, `tauri-build =2.7.2`.
- `src-tauri/tauri.conf.json` — single `main` window on the bootstrap
  surface; loopback-only CSP; bundle disabled (S15-09 owns packaging).
- `src-tauri/src/lifecycle.rs` — owned supervisor child, readiness polling,
  bootstrap renderer, `LifecycleController` (cold start / cancel / shutdown),
  navigation-guard helpers, regression tests.
- `src-tauri/src/` — `main.rs` + `lib.rs`: bootstrap-first host, same-window
  bootstrap→SPA transition on readiness, second-launch refusal via the
  supervisor lock, owned-tree shutdown on close.

## Disposable lifecycle smoke

Point the app at a staged package copy plus a fresh data root (never the
owner `%LOCALAPPDATA%\Projecta` tree):

- `PROJECTA_DESKTOP_PACKAGE_ROOT` → staged package root (bundled
  `runtime/python/python.exe` + `projecta/scripts/projecta_local.py`).
- `PROJECTA_LAUNCHER_DATA_ROOT` → fresh disposable data root.
- `PROJECTA_S15_03_API_PORT` (default `18732`; `PROJECTA_S15_02_API_PORT`
  still honoured as fallback).

The app installs nothing itself: pre-run the existing `install` subcommand on
the disposable roots once, then launch the desktop binary. Closing the window
stops only the owned tree; a second app launch against the same roots refuses
(`RUNTIME_ALREADY_ACTIVE`) without a second backend/TDB2 writer.
