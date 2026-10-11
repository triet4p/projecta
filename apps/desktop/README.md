# Projecta Desktop (Tauri v2 slice — S15-02)

One native Tauri v2 window over the existing loopback Application API SPA.
This slice owns only the rendering surface; the backend stays externally
owned (started separately against disposable roots) and supervisor
ownership, first-run, recovery, trust hardening, and packaging belong to
S15-03…S15-09.

## Layout

- `package.json` — npm scripts (`tauri dev` / `tauri build`); pinned
  `@tauri-apps/cli 2.12.2` + `@tauri-apps/api 2.12.3`.
- `src-tauri/Cargo.toml` — pinned `tauri =2.12.3`, `tauri-build =2.7.2`.
- `src-tauri/tauri.conf.json` — single `main` window on
  `http://127.0.0.1:18732/`; loopback-only CSP; bundle disabled (S15-09 owns
  packaging).
- `src-tauri/src/` — `main.rs` + `lib.rs`: no Tauri commands, one-window
  navigation guard refusing foreign origins inside the privileged view,
  ordinary close that stops nothing externally owned.

## Disposable proof backend

The slice never starts services itself. Point it at an externally started
disposable backend with `PROJECTA_S15_02_API_PORT` (default `18732`) and
close the window when done; externally owned services keep running.
