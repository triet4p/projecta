// Projecta S15-03 desktop host: bootstrap-first window over an app-owned service tree.
//
// One main window renders the locally bundled bootstrap surface first, then
// navigates the SAME window to the owned loopback Application API origin on
// real readiness. The app spawns exactly one supervisor child (the existing
// local CLI) and stops only that child on cancel/close via the existing
// `stop` subcommand. No Tauri command is registered: the WebView has no
// native bridge in this slice, so there is no capability to scope yet
// (S15-06 owns the manifest). Explicit control/recovery/error UX belongs to
// S15-04/S15-05; packaging belongs to S15-09.

mod lifecycle;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};
use lifecycle::{
    BOOTSTRAP_SCHEME, LifecycleController, LifecyclePaths, LifecycleState, MAIN_WINDOW_LABEL,
    api_origin, is_allowed_navigation, render_bootstrap,
};
use tauri::{Manager, Url};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let origin = api_origin();
    let api_port: u16 = origin
        .rsplit(':')
        .next()
        .and_then(|tail| tail.trim_end_matches('/').parse::<u16>().ok())
        .unwrap_or(lifecycle::DEFAULT_API_PORT);
    let paths = LifecyclePaths::resolve();
    let lifecycle = Arc::new(LifecycleController::new(paths, api_port));
    let closing = Arc::new(AtomicBool::new(false));

    // The privileged main view renders only the bundled bootstrap surface
    // first, then the owned loopback API origin. This plugin refuses any
    // other navigation inside that view; S15-07 owns explicit external-link
    // handling.
    let guard_origin = origin.clone();
    let guard: tauri::plugin::TauriPlugin<tauri::Wry> =
        tauri::plugin::Builder::new("s15-03-navigation-guard")
            .on_navigation(move |_webview, url| is_allowed_navigation(url, &guard_origin))
            .build();

    // Bootstrap protocol: serves the locally bundled lifecycle surface with
    // the live snapshot (no network fetch, no secrets, sanitized diagnostics).
    let proto_lifecycle = lifecycle.clone();
    let proto_origin = origin.clone();

    let startup_lifecycle = lifecycle.clone();
    let close_lifecycle = lifecycle.clone();
    let close_flag = closing.clone();

    tauri::Builder::default()
        .plugin(guard)
        .register_uri_scheme_protocol(BOOTSTRAP_SCHEME, move |_ctx, _request| {
            let (state, code, pid) = proto_lifecycle.snapshot();
            let html = render_bootstrap(state, code.as_deref(), pid, &proto_origin);
            tauri::http::Response::builder()
                .header("Content-Type", "text/html")
                .body(html.into_bytes())
                .unwrap()
        })
        .setup(move |app| {
            // App launch is the Start binding: cold start runs off the event
            // loop so the bootstrap surface stays responsive.
            let worker = startup_lifecycle.clone();
            let handle = worker.take_startup_handle();
            debug_assert!(handle.is_none());
            let startup_thread = std::thread::spawn(move || worker.cold_start());
            startup_lifecycle.set_startup_handle(startup_thread);

            // Same-window transition: on real readiness, navigate the main
            // view from bootstrap to the owned loopback SPA. Single attempt,
            // no retry — failure leaves the sanitized bootstrap failure page.
            let watcher = startup_lifecycle.clone();
            let watcher_origin = origin.clone();
            let watcher_app = app.handle().clone();
            std::thread::spawn(move || {
                let started = Instant::now();
                let limit = lifecycle::STARTUP_DEADLINE + Duration::from_secs(60);
                loop {
                    match watcher.state() {
                        LifecycleState::Ready => {
                            if let Some(view) =
                                watcher_app.get_webview_window(MAIN_WINDOW_LABEL)
                            {
                                if let Ok(url) = watcher_origin.parse::<Url>() {
                                    let _ = view.navigate(url);
                                }
                            }
                            break;
                        }
                        LifecycleState::Failed
                        | LifecycleState::Stopped
                        | LifecycleState::ShutdownFailed => break,
                        LifecycleState::Bootstrap | LifecycleState::Starting => {}
                    }
                    if started.elapsed() > limit {
                        break;
                    }
                    std::thread::sleep(Duration::from_millis(500));
                }
            });
            Ok(())
        })
        .on_window_event(move |window, event| {
            // Ordinary close: cancel an in-flight startup or gracefully stop
            // the owned tree (reverse order is the supervisor's own
            // shutdown), then close. Only owned children are ever signalled;
            // foreign processes are never touched; data is always retained.
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if close_flag.swap(true, Ordering::SeqCst) {
                    return;
                }
                api.prevent_close();
                let win = window.clone();
                let shutdown = close_lifecycle.clone();
                std::thread::spawn(move || {
                    shutdown.request_cancel();
                    if let Some(startup) = shutdown.take_startup_handle() {
                        let _ = startup.join();
                    }
                    shutdown.shutdown();
                    let _ = win.close();
                });
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::lifecycle::{DEFAULT_API_PORT, LOOPBACK_HOST, bootstrap_url};
    use super::{api_origin, is_allowed_navigation};

    #[test]
    fn api_origin_stays_loopback_http() {
        let origin = api_origin();
        assert!(
            origin.starts_with(&format!("http://{LOOPBACK_HOST}:")),
            "unexpected API origin: {origin}"
        );
        assert!(!origin.contains("https://"), "slice must not upgrade to TLS");
    }

    #[test]
    fn default_port_matches_launcher_api_port() {
        assert_eq!(DEFAULT_API_PORT, 18732);
    }

    #[test]
    fn navigation_refuses_foreign_origins() {
        let origin = format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/");
        let allowed: url::Url = origin.parse().expect("valid origin");
        assert!(is_allowed_navigation(&allowed, &origin));
        let bootstrap: url::Url = bootstrap_url().parse().expect("valid bootstrap URL");
        assert!(is_allowed_navigation(&bootstrap, &origin));
        for raw in [
            "https://example.test/",
            "http://example.test/",
            "http://127.0.0.1:18080/",
            "http://localhost:18732/",
            "file:///C:/Windows/win.ini",
            "tauri://localhost/",
        ] {
            let url: url::Url = raw.parse().expect("valid URL");
            assert!(
                !is_allowed_navigation(&url, &origin),
                "must refuse navigation to {raw}"
            );
        }
    }
}
