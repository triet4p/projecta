// Projecta S15-03/04 desktop host: bootstrap-first window over an app-owned service tree.
//
// One main window renders the local first-run form or lifecycle surface, then
// navigates the SAME window to the owned loopback Application API origin on
// real readiness. The first-run form provisions workspace state before the app
// starts exactly one supervisor child (the existing local CLI); close stops
// only that child via the existing `stop` subcommand. No Tauri command is
// registered: the WebView has no native bridge in this slice, so there is no
// capability to scope yet (S15-06 owns the manifest). Expanded recovery/error
// UX belongs to S15-05; packaging belongs to S15-09.

mod lifecycle;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};
use lifecycle::{
    BOOTSTRAP_SCHEME, LifecycleController, LifecyclePaths, LifecycleState, MAIN_WINDOW_LABEL,
    api_origin, is_allowed_navigation, render_bootstrap, render_first_run,
};
use tauri::{Manager, Url};

/// Default first-run display name offered as the form placeholder. This mirrors
/// the launcher's own `FIRST_RUN_DISPLAY_NAME` so the placeholder text is never
/// invented here; the authoritative default stays in the Python launcher.
const FIRST_RUN_DEFAULT_NAME: &str = "My Projecta Workspace";

/// Build a text/html response for the bootstrap surface.
fn html_response(html: String) -> tauri::http::Response<Vec<u8>> {
    tauri::http::Response::builder()
        .header("Content-Type", "text/html")
        .body(html.into_bytes())
        .unwrap()
}

/// Read one query value from a `application/x-www-form-urlencoded` string.
fn query_param(query: &str, key: &str) -> Option<String> {
    query
        .split('&')
        .filter_map(|pair| pair.split_once('='))
        .find(|(name, _)| *name == key)
        .map(|(_, value)| percent_decode(value))
}

/// Decode `+` and `%XX` escapes from a form-encoded value.
fn percent_decode(value: &str) -> String {
    let bytes = value.replace('+', " ");
    let mut decoded: Vec<u8> = Vec::with_capacity(bytes.len());
    let mut raw = bytes.as_bytes().iter().copied();
    while let Some(byte) = raw.next() {
        if byte == b'%' {
            let high = raw.next().and_then(|c| (c as char).to_digit(16));
            let low = raw.next().and_then(|c| (c as char).to_digit(16));
            match (high, low) {
                (Some(high), Some(low)) => decoded.push((high * 16 + low) as u8),
                _ => decoded.push(byte),
            }
        } else {
            decoded.push(byte);
        }
    }
    String::from_utf8_lossy(&decoded).into_owned()
}

/// Provision the first-run workspace from the same main window and, on success,
/// continue into the ordinary cold start so the user sees one continuous
/// journey. Failure re-renders the form with a finite refusal code.
///
/// A refused name produces NO writes: the Rust validation runs before any child
/// process is spawned, so there is no partial customer state to clean up.
fn provision_response(
    lifecycle: &std::sync::Arc<LifecycleController>,
    name: &str,
    api_origin: &str,
) -> tauri::http::Response<Vec<u8>> {
    if let Err(code) = lifecycle.provision_first_run(name) {
        let html = render_first_run(FIRST_RUN_DEFAULT_NAME, Some(&code));
        return html_response(html);
    }
    // The workspace now exists; start the owned tree exactly as an existing
    // workspace would. The existing watcher navigates the SAME window to the
    // loopback SPA on real readiness.
    lifecycle.spawn_cold_start();
    let (state, code, pid) = lifecycle.snapshot();
    html_response(render_bootstrap(state, code.as_deref(), pid, api_origin))
}

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

    // Bootstrap protocol serves the local first-run form or the lifecycle
    // surface with the live snapshot (no network fetch, no secrets). The
    // user's name is present in the form field and submitted through this
    // protocol request; it is not copied into diagnostics or responses.
    let proto_lifecycle = lifecycle.clone();
    let proto_origin = origin.clone();

    let close_lifecycle = lifecycle.clone();
    let close_flag = closing.clone();
    // The provision path and the setup path both start the owned tree, so the
    // protocol handler and `setup` hold their own handles.
    let provision_starter = lifecycle.clone();
    let setup_lifecycle = lifecycle.clone();

    tauri::Builder::default()
        .plugin(guard)
        .register_uri_scheme_protocol(BOOTSTRAP_SCHEME, move |_ctx, request| {
            // A first-run submission reaches this handler through its protocol
            // request. Cancel is a no-write dismissal; create validates and
            // provisions. The name is carried by the form request but never
            // echoed raw into the response.
            if request.uri().path() == "/provision" {
                let query = request.uri().query().unwrap_or_default();
                let intent = query_param(query, "intent").unwrap_or_default();
                let name = query_param(query, "name");
                if intent == "cancel" {
                    let html = render_first_run(FIRST_RUN_DEFAULT_NAME, None);
                    return html_response(html);
                }
                if let Some(trimmed) = name.as_deref().map(str::trim).filter(|v| !v.is_empty()) {
                    return provision_response(&provision_starter, trimmed, &proto_origin);
                }
                let invalid =
                    render_first_run(FIRST_RUN_DEFAULT_NAME, Some("WORKSPACE_NAME_INVALID"));
                return html_response(invalid);
            }
            let html = if proto_lifecycle.is_first_run() {
                render_first_run(FIRST_RUN_DEFAULT_NAME, None)
            } else {
                let (state, code, pid) = proto_lifecycle.snapshot();
                render_bootstrap(state, code.as_deref(), pid, &proto_origin)
            };
            html_response(html)
        })
        .setup(move |app| {
            // First-run vs reopen: an existing workspace starts immediately
            // (the S15-03 Start binding); a data root with no workspace shows the
            // in-window first-run form instead, and only provisions when the
            // user submits a valid name. No service tree is started while the
            // form is unanswered, so a cancelled or refused first run leaves no
            // partial customer state behind.
            let first_run = setup_lifecycle.clone();
            if !first_run.is_first_run() {
                first_run.spawn_cold_start();
            }


            // Same-window transition: on real readiness, navigate the main
            // view from bootstrap to the owned loopback SPA. Single attempt,
            // no retry — failure leaves the sanitized bootstrap failure page.
            let watcher = setup_lifecycle.clone();
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
