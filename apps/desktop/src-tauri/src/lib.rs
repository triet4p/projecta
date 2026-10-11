// Projecta S15-03/05 desktop host: bootstrap-first window over an app-owned
// service tree, with the runtime-control surface in the SAME main window.
//
// One main window renders the local first-run form, the lifecycle surface
// (Start/Stop, bounded recovery, sanitized diagnostics for the contract's
// states), or the owned loopback Application API SPA — navigating between
// them in the same WebView on real readiness, post-ready failure, and user
// actions. The first-run form provisions workspace state before the app
// starts exactly one supervisor child (the existing local CLI); close stops
// only that child via the existing `stop` subcommand. The native Runtime menu
// binds Start/Stop/Show-controls to the same lifecycle operations so the
// controls stay reachable after the window shows the SPA. No Tauri command is
// registered: the WebView has no native bridge in this slice, so there is no
// capability to scope yet (S15-06 owns the manifest). Packaging belongs to
// S15-09.

mod lifecycle;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use lifecycle::{
    BOOTSTRAP_SCHEME, BOOTSTRAP_SURFACE_URL, LifecycleController, LifecyclePaths, LifecycleState,
    MAIN_WINDOW_LABEL, StopOutcome, api_origin, is_allowed_navigation, render_bootstrap,
    render_first_run, runtime_menu_action, RuntimeMenuAction,
};
use tauri::menu::{Menu, MenuItem, Submenu};
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

/// Absolute URL of the bundled lifecycle surface as the platform expresses it
/// (the exact navigation guard already accepts). Used for every surface
/// navigation: control submissions, live refresh during `starting`, and the
/// native Runtime menu's "show controls" action — always the SAME main window.
fn surface_url() -> Url {
    Url::parse(BOOTSTRAP_SURFACE_URL).expect("valid bundled surface URL")
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
    html_response(render_bootstrap(&lifecycle.snapshot(), api_origin))
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
    // Runtime intent handling: Start/Stop are the existing supervisor
    // operations, bound in the SAME window through this bundled surface. Both
    // run off the protocol thread so the window stays responsive.
    let runtime_intent = lifecycle.clone();
    let runtime_origin = origin.clone();

    let close_lifecycle = lifecycle.clone();
    let close_flag = closing.clone();
    // The provision path and the setup path both start the owned tree, so the
    // protocol handler and `setup` hold their own handles.
    let provision_starter = lifecycle.clone();
    let setup_lifecycle = lifecycle.clone();
    // Menu actions need their own handle onto the same controller.
    let menu_lifecycle = lifecycle.clone();

    tauri::Builder::default()
        .plugin(guard)
        .register_uri_scheme_protocol(BOOTSTRAP_SCHEME, move |ctx, request| {
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
            // Lifecycle surface controls (Start/Stop) submit here as a plain
            // form navigation. Every action is bounded, single-attempt, and
            // user-initiated; nothing restarts automatically.
            if request.uri().path() == "/runtime" {
                let query = request.uri().query().unwrap_or_default();
                let intent = query_param(query, "intent").unwrap_or_default();
                match intent.as_str() {
                    "start" => {
                        // A refused start (already starting/ready, or awaiting
                        // first-run provisioning) changes nothing.
                        runtime_intent.user_start();
                    }
                    "stop" => {
                        // Mark the stop in flight before rendering the response,
                        // so this navigation's own render is live (refreshing)
                        // rather than a stale pre-action page.
                        runtime_intent.begin_user_stop();
                        let stopper = runtime_intent.clone();
                        let stop_app = ctx.app_handle().clone();
                        std::thread::spawn(move || {
                            let _: StopOutcome = stopper.complete_user_stop();
                            // Re-render the surface with the manager's own
                            // terminal outcome.
                            if let Some(view) =
                                stop_app.get_webview_window(MAIN_WINDOW_LABEL)
                            {
                                let _ = view.navigate(surface_url());
                            }
                        });
                    }
                    _ => {}
                }
                let snapshot = runtime_intent.snapshot();
                return html_response(render_bootstrap(&snapshot, &runtime_origin));
            }
            let html = if proto_lifecycle.is_first_run() {
                render_first_run(FIRST_RUN_DEFAULT_NAME, None)
            } else {
                render_bootstrap(&proto_lifecycle.snapshot(), &proto_origin)
            };
            html_response(html)
        })
        .menu(|app| {
            // Native Runtime menu keeps Start/Stop/Show-controls reachable in
            // the main window in every state, including while the same window
            // serves the SPA. It binds only the existing §3.1 operations and
            // adds no Tauri command or capability.
            let start = MenuItem::with_id(app, "runtime-start", "Start runtime", true, None::<&str>)?;
            let stop = MenuItem::with_id(app, "runtime-stop", "Stop runtime", true, None::<&str>)?;
            let show =
                MenuItem::with_id(app, "runtime-show", "Show runtime controls", true, None::<&str>)?;
            let runtime =
                Submenu::with_items(app, "Runtime", true, &[&start, &stop, &show])?;
            Menu::with_items(app, &[&runtime])
        })
        .on_menu_event(move |app, event| {
            match runtime_menu_action(event.id().0.as_str()) {
                RuntimeMenuAction::Start => {
                    if menu_lifecycle.user_start() {
                        if let Some(view) = app.get_webview_window(MAIN_WINDOW_LABEL) {
                            let _ = view.navigate(surface_url());
                        }
                    }
                }
                RuntimeMenuAction::Stop => {
                    // Mark the stop in flight BEFORE navigating, so the surface
                    // render the user sees is a live view of the real stop
                    // instead of a stale pre-action render.
                    menu_lifecycle.begin_user_stop();
                    // Show the surface first so the stop is observable in the
                    // same window, then run the bounded stop off the UI thread.
                    if let Some(view) = app.get_webview_window(MAIN_WINDOW_LABEL) {
                        let _ = view.navigate(surface_url());
                    }
                    let stopper = menu_lifecycle.clone();
                    std::thread::spawn(move || {
                        let _: StopOutcome = stopper.complete_user_stop();
                    });
                }
                RuntimeMenuAction::ShowControls => {
                    if let Some(view) = app.get_webview_window(MAIN_WINDOW_LABEL) {
                        let _ = view.navigate(surface_url());
                    }
                }
                RuntimeMenuAction::None => {}
            }
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
            // view from the lifecycle surface to the owned loopback SPA; if the
            // owned manager then exits after that ready episode, adopt its own
            // terminal outcome and navigate the SAME window back to the
            // lifecycle surface. Single attempt, no retry — failure leaves the
            // sanitized failure surface, and recovery stays user-initiated.
            let watcher = setup_lifecycle.clone();
            let watcher_origin = origin.clone();
            let watcher_app = app.handle().clone();
            std::thread::spawn(move || {
                let mut spa_shown = false;
                loop {
                    match watcher.state() {
                        LifecycleState::Ready => {
                            if !spa_shown {
                                if let Some(view) =
                                    watcher_app.get_webview_window(MAIN_WINDOW_LABEL)
                                {
                                    if let Ok(url) = watcher_origin.parse::<Url>() {
                                        let _ = view.navigate(url);
                                    }
                                }
                                spa_shown = true;
                            }
                            // Post-ready failure: the manager owns service
                            // supervision, so its exit is the failure signal.
                            if !watcher.owned_supervisor_alive() {
                                watcher.adopt_supervisor_exit_after_ready();
                                if let Some(view) =
                                    watcher_app.get_webview_window(MAIN_WINDOW_LABEL)
                                {
                                    let _ = view.navigate(surface_url());
                                }
                                spa_shown = false;
                            }
                        }
                        LifecycleState::Bootstrap | LifecycleState::Starting => {
                            spa_shown = false;
                        }
                        LifecycleState::Degraded
                        | LifecycleState::Stopped
                        | LifecycleState::Failed
                        | LifecycleState::ShutdownFailed => {
                            spa_shown = false;
                        }
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
