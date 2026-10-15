// Projecta S15-03/05/06/07 desktop host: one window over an app-owned service
// tree with the workspace-management surface in the SAME window and an
// explicit WebView/native trust boundary.
//
// One main window renders the local workspace-management surface (the
// workspace record, the eight real initialization steps, bounded Start/Retry/
// Stop/Open controls, the inline create card, and sanitized diagnostics for
// the contract's states) or the owned loopback Application API SPA — navigating
// between the two top-level surfaces in the same WebView on real readiness,
// post-ready failure, and user actions. The ready SPA carries one desktop-only
// `Manage workspace` action in its own header that navigates this same window
// back to the management surface (the host's `BOOTSTRAP_SURFACE_URL` root, the
// URL its guard already admits); it stops, restarts, and reseeds nothing.
// Opening the app starts the owned supervisor child for an existing workspace
// by itself; the inline create card
// provisions a fresh workspace first, and close cancels an in-flight creation
// and stops only that child via the existing `stop` subcommand. The lifecycle
// surface owns every control (Start/Retry/Stop/Open and the inline create
// card) and the host registers no native menu bar: the window keeps only its
// OS title bar and standard minimize/maximize/close controls.
//
// Trust boundary (S15-06): the main window is created here — not from a
// second declarative window — so its boundary handlers are explicit: it opens
// only the bundled bootstrap surface, its navigation guard admits only the
// bundled surface and the owned loopback API origin, and it denies every
// secondary window. A new-window request for an allowed web URL is the
// explicit external-link hand-off (S15-07): it leaves for the system browser
// and is never rendered here. The window owns its download destination
// (S15-07) so a portable export lands in the platform download folder, or in
// an explicitly configured disposable root for proof runs. No Tauri command
// is registered and no capability is granted: the WebView has no native
// bridge at all (empty capability manifest, `withGlobalTauri: false`), and
// supervisor operations stay in the existing local CLI. Packaging belongs
// to S15-09.

mod lifecycle;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use lifecycle::{
    BOOTSTRAP_SCHEME, BOOTSTRAP_SURFACE_URL, LifecycleController, LifecyclePaths, LifecycleState,
    MAIN_WINDOW_LABEL, StopOutcome, ThemeMode, api_origin, download_directory, download_destination,
    external_link_allowed, is_allowed_navigation, main_window_url, new_window_allowed,
    open_in_system_browser, render_workspace_management,
};
use tauri::webview::{NewWindowResponse, PermissionKind, PermissionResponse};
use tauri::{Manager, Url, WebviewUrl, WebviewWindowBuilder};

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
/// post-ready return to the surface — always the SAME main window.
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

/// Accept the workspace-creation request from the SAME main window (the inline
/// card of the workspace-management surface) and return immediately: the
/// accepted request sets the real `starting` state and in-flight marker, so
/// this very response renders the creating overlay, and its own 2-second
/// refresh observes the real outcome. On success the worker continues into the
/// ordinary cold start, so the user sees one continuous journey on that same
/// surface; a failure dismisses the overlay and the management surface shows
/// the finite outcome.
///
/// A refused name produces NO writes and NO child: the Rust validation runs
/// before any child process is spawned, so there is no partial customer state
/// to clean up.
fn provision_response(
    lifecycle: &std::sync::Arc<LifecycleController>,
    name: &str,
) -> tauri::http::Response<Vec<u8>> {
    let refusal = lifecycle.begin_provision(name).err();
    let mut view = lifecycle.management_view();
    // `PROVISION_CANCELLED` is the close path stopping the owned child, not a
    // user-visible refusal: the window is going away.
    view.refusal = refusal.filter(|code| code != "PROVISION_CANCELLED");
    html_response(render_workspace_management(&view))
}
pub const THEME_CUSTOM_HEADER: &str = "X-Projecta-Theme-Request";
pub const THEME_CUSTOM_HEADER_VALUE: &str = "1";

pub fn is_trusted_theme_origin(origin: &str) -> bool {
    origin == "http://127.0.0.1:18732"
        || origin == "http://projecta-bootstrap.localhost"
        || origin == "projecta-bootstrap://localhost"
}

pub fn handle_preferences_theme_request<F>(
    request: &tauri::http::Request<Vec<u8>>,
    controller: &LifecycleController,
    mut on_theme_change: F,
) -> tauri::http::Response<Vec<u8>>
where
    F: FnMut(ThemeMode),
{
    let origin = request
        .headers()
        .get("Origin")
        .and_then(|v| v.to_str().ok())
        .unwrap_or_default();

    if origin.is_empty() || !is_trusted_theme_origin(origin) {
        return tauri::http::Response::builder()
            .status(403)
            .header("Content-Type", "application/json")
            .body(b"{\"error\":\"FORBIDDEN_ORIGIN\"}".to_vec())
            .unwrap();
    }

    if request.method() == "OPTIONS" {
        return tauri::http::Response::builder()
            .status(204)
            .header("Access-Control-Allow-Origin", origin)
            .header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            .header(
                "Access-Control-Allow-Headers",
                "Content-Type, X-Projecta-Theme-Request",
            )
            .body(Vec::new())
            .unwrap();
    }

    // Require custom header for both GET and POST to guard against simple-request CSRF
    let custom_header = request
        .headers()
        .get(THEME_CUSTOM_HEADER)
        .and_then(|v| v.to_str().ok());
    if custom_header != Some(THEME_CUSTOM_HEADER_VALUE) {
        return tauri::http::Response::builder()
            .status(403)
            .header("Content-Type", "application/json")
            .header("Access-Control-Allow-Origin", origin)
            .body(b"{\"error\":\"FORBIDDEN_HEADER\"}".to_vec())
            .unwrap();
    }

    if request.method() == "GET" {
        let current_mode = controller.theme_mode();
        let resp_body = serde_json::json!({ "themeMode": current_mode.as_str() }).to_string();
        return tauri::http::Response::builder()
            .status(200)
            .header("Content-Type", "application/json")
            .header("Access-Control-Allow-Origin", origin)
            .body(resp_body.into_bytes())
            .unwrap();
    }

    if request.method() == "POST" {
        let mut mode_to_set = None;
        if let Ok(body_str) = std::str::from_utf8(request.body()) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(body_str) {
                if let Some(m) = json.get("themeMode").and_then(|v| v.as_str()) {
                    mode_to_set = ThemeMode::from_str_loose(m);
                } else if let Some(m) = json.get("mode").and_then(|v| v.as_str()) {
                    mode_to_set = ThemeMode::from_str_loose(m);
                }
            }
        }
        if mode_to_set.is_none() {
            let query = request.uri().query().unwrap_or_default();
            if let Some(m) = query_param(query, "mode") {
                mode_to_set = ThemeMode::from_str_loose(&m);
            }
        }

        if let Some(mode) = mode_to_set {
            let _ = controller.set_theme_mode(mode);
            on_theme_change(mode);
            let resp_body = serde_json::json!({ "themeMode": mode.as_str() }).to_string();
            return tauri::http::Response::builder()
                .status(200)
                .header("Content-Type", "application/json")
                .header("Access-Control-Allow-Origin", origin)
                .body(resp_body.into_bytes())
                .unwrap();
        } else {
            return tauri::http::Response::builder()
                .status(400)
                .header("Content-Type", "application/json")
                .header("Access-Control-Allow-Origin", origin)
                .body(b"{\"error\":\"THEME_MODE_INVALID\"}".to_vec())
                .unwrap();
        }
    }

    // Any other method: 405 Method Not Allowed
    tauri::http::Response::builder()
        .status(405)
        .header("Content-Type", "application/json")
        .header("Allow", "GET, POST, OPTIONS")
        .header("Access-Control-Allow-Origin", origin)
        .body(b"{\"error\":\"METHOD_NOT_ALLOWED\"}".to_vec())
        .unwrap()
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
    // other navigation inside that view; an explicit external-link request is
    // handled by the new-window hand-off to the system browser instead.
    let guard_origin = origin.clone();
    let guard: tauri::plugin::TauriPlugin<tauri::Wry> =
        tauri::plugin::Builder::new("s15-03-navigation-guard")
            .on_navigation(move |_webview, url| is_allowed_navigation(url, &guard_origin))
            .build();

    // Bootstrap protocol serves the workspace-management surface (real
    // initialization steps, workspace record, inline create card, runtime
    // controls) with live observations (no network fetch, no secrets). The
    // user's name is present in the form field and submitted through this
    // protocol request; it is not copied into diagnostics or responses.
    let proto_lifecycle = lifecycle.clone();
    // The management surface's "Open project workspace" action needs the
    // loopback origin as its own clone: the guard and the readiness watcher
    // hold theirs.
    let surface_origin = origin.clone();
    // Runtime intent handling: Start/Stop/Cancel/Open are the existing
    // supervisor operations and the same-window SPA navigation, bound in the
    // SAME window through this bundled surface. They run off the protocol
    // thread so the window stays responsive.
    let runtime_intent = lifecycle.clone();

    let close_lifecycle = lifecycle.clone();
    let close_flag = closing.clone();
    // The provision path and the setup path both start the owned tree, so the
    // protocol handler and `setup` hold their own handles.
    let provision_starter = lifecycle.clone();
    let setup_lifecycle = lifecycle.clone();

    tauri::Builder::default()
        .plugin(guard)
        .register_uri_scheme_protocol(BOOTSTRAP_SCHEME, move |ctx, request| {
            // A create submission reaches this handler through its protocol
            // request. Cancel is a no-write dismissal; create validates and
            // provisions. The name is carried by the form request but never
            // echoed raw into the response.
            if request.uri().path() == "/provision" {
                let query = request.uri().query().unwrap_or_default();
                let intent = query_param(query, "intent").unwrap_or_default();
                let name = query_param(query, "name");
                if intent == "cancel" {
                    return html_response(render_workspace_management(
                        &proto_lifecycle.management_view(),
                    ));
                }
                if let Some(trimmed) = name.as_deref().map(str::trim).filter(|v| !v.is_empty()) {
                    return provision_response(&provision_starter, trimmed);
                }
                let mut view = proto_lifecycle.management_view();
                view.refusal = Some("WORKSPACE_NAME_INVALID".to_string());
                return html_response(render_workspace_management(&view));
            }
            // Scoped desktop UI theme preference endpoint: accessible only to
            // trusted app-owned origins (loopback SPA and bundled bootstrap surface).
            // Saves/reads deterministic `<data_root>/config/ui-preferences.json` and updates window theme.
            if request.uri().path() == "/preferences/theme" || request.uri().path() == "/preferences" {
                return handle_preferences_theme_request(&request, &runtime_intent, |mode| {
                    if let Some(win) = ctx.app_handle().get_webview_window(MAIN_WINDOW_LABEL) {
                        let t = match mode {
                            ThemeMode::Light => Some(tauri::Theme::Light),
                            ThemeMode::Dark => Some(tauri::Theme::Dark),
                            ThemeMode::System => None,
                        };
                        let _ = win.set_theme(t);
                    }
                });
            }
            // Management-surface controls (Start/Retry, Stop/Cancel, Open)
            // submit here as a plain form navigation. Every action is bounded,
            // single-attempt, and user-initiated; nothing restarts
            // automatically.
            if request.uri().path() == "/runtime" {
                let query = request.uri().query().unwrap_or_default();
                let intent = query_param(query, "intent").unwrap_or_default();
                match intent.as_str() {
                    "start" => {
                        // A refused start (already starting/ready, or awaiting
                        // workspace creation) changes nothing.
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
                    "open" => {
                        // Enter the second top-level surface — the existing
                        // project workspace SPA — in this SAME window, only
                        // when the owned runtime is objectively ready.
                        if runtime_intent.state() == LifecycleState::Ready {
                            if let Some(view) = ctx.app_handle().get_webview_window(MAIN_WINDOW_LABEL)
                            {
                                if let Ok(url) = surface_origin.parse::<Url>() {
                                    let _ = view.navigate(url);
                                }
                            }
                        }
                    }
                    "theme" => {
                        let mode_param = query_param(query, "mode").unwrap_or_default();
                        if let Some(mode) = ThemeMode::from_str_loose(&mode_param) {
                            let _ = runtime_intent.set_theme_mode(mode);
                            if let Some(win) = ctx.app_handle().get_webview_window(MAIN_WINDOW_LABEL) {
                                let t = match mode {
                                    ThemeMode::Light => Some(tauri::Theme::Light),
                                    ThemeMode::Dark => Some(tauri::Theme::Dark),
                                    ThemeMode::System => None,
                                };
                                let _ = win.set_theme(t);
                            }
                        }
                    }
                    _ => {}
                }
                return html_response(render_workspace_management(
                    &runtime_intent.management_view(),
                ));
            }
            html_response(render_workspace_management(
                &proto_lifecycle.management_view(),
            ))
        })
        .setup(move |app| {
            // The privileged main window is the only trusted surface. It is
            // created here — never from a second declarative window — so its
            // WebView-level boundary handlers are explicit and reviewable: it
            // opens exactly the bundled bootstrap surface, refuses every
            // secondary window, and grants no sensitive web permission. The
            // window fields mirror the single declarative entry this replaces.
            let initial_theme = match setup_lifecycle.theme_mode() {
                ThemeMode::Light => Some(tauri::Theme::Light),
                ThemeMode::Dark => Some(tauri::Theme::Dark),
                ThemeMode::System => None,
            };
            let main_window = WebviewWindowBuilder::new(
                app,
                MAIN_WINDOW_LABEL,
                WebviewUrl::CustomProtocol(main_window_url()),
            )
            .title("Projecta")
            .inner_size(1280.0, 860.0)
            .min_inner_size(1024.0, 640.0)
            .resizable(true)
            .center()
            .theme(initial_theme)
            .on_new_window(|url, _features| {
                // S15-07 external-link path: a link that would open a second
                // window (`window.open`, `target="_blank"`) is an explicit
                // hand-off to the system browser for allowed web URLs. It is
                // never rendered in a second app window and never navigates
                // this privileged view; every other request is refused
                // outright, exactly as before. The launch runs off the UI
                // thread so the window stays responsive.
                if external_link_allowed(&url) {
                    let launched = url.clone();
                    std::thread::spawn(move || {
                        let _ = open_in_system_browser(&launched);
                    });
                }
                if new_window_allowed(&url) {
                    NewWindowResponse::Allow
                } else {
                    NewWindowResponse::Deny
                }
            })
            .on_download(|_webview, event| {
                // S15-07 download path: the portable-export archive arrives
                // here as a same-origin blob download. The host owns the
                // destination so the archive lands in a deterministic place
                // when a disposable root is configured, while a normal run
                // keeps the platform's own download folder untouched. The
                // requested file name is preserved; the download never
                // navigates the privileged view.
                if let tauri::webview::DownloadEvent::Requested { destination, .. } = event {
                    if let Some(target) =
                        download_destination(destination, download_directory().as_deref())
                    {
                        *destination = target;
                    }
                }
                true
            })
            .on_permission_request(|_webview, kind| match kind {
                // The desktop needs no sensitive web permission in any state:
                // the bundled surfaces use none and the loopback SPA asks for
                // none. Automatic downloads stay at the platform default so
                // the S15-07 export download works without a capability.
                PermissionKind::AutomaticDownloads => PermissionResponse::Default,
                _ => PermissionResponse::Deny,
            })
            .build()?;
            let _ = main_window;

            // The management surface is the only first view. An existing
            // workspace starts its owned runtime immediately — opening the app
            // is the start action, and there is no separate Start screen or
            // required Start click — while a data root with no workspace shows
            // the same surface with the inline create card and starts nothing
            // until the user submits a valid name. No service tree is started
            // for an unprovisioned or refused workspace, so a cancelled or
            // refused creation leaves no partial customer state behind.
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
            // Ordinary close at ANY stage — before creation, during creation,
            // during startup, ready, degraded, failed, or waiting for an
            // explicit stop retry — cancels and joins this instance's workers,
            // then stops only its confirmed owned tree. The controller handles
            // the handle-publication race before this window exits.
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if close_flag.swap(true, Ordering::SeqCst) {
                    return;
                }
                api.prevent_close();
                let win = window.clone();
                let shutdown = close_lifecycle.clone();
                std::thread::spawn(move || {
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
    use super::*;
    use super::lifecycle::{DEFAULT_API_PORT, LOOPBACK_HOST, bootstrap_url, LifecycleController, LifecyclePaths, ThemeMode};
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

    fn disposable_theme_root(label: &str) -> (std::path::PathBuf, LifecycleController, LifecyclePaths) {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|elapsed| elapsed.as_nanos())
            .unwrap_or(0);
        let root = std::env::temp_dir().join(format!("{label}-{unique}"));
        std::fs::create_dir_all(&root).expect("disposable theme root");
        let paths = LifecyclePaths {
            supervisor_exe: std::path::PathBuf::from("C:/nonexistent/ProjectaLocal.exe"),
            local_app_data: root.clone(),
            data_root: root.clone(),
        };
        let controller = LifecycleController::new(Some(paths.clone()), DEFAULT_API_PORT);
        (root, controller, paths)
    }

    #[test]
    fn trusted_origin_get_and_post_succeed_and_persist() {
        let (root, controller, paths) = disposable_theme_root("s15-07-theme-trusted");
        let mut window_theme = None;

        // Initial GET returns default System
        let get_req = tauri::http::Request::builder()
            .method("GET")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header("Origin", "http://127.0.0.1:18732")
            .header(THEME_CUSTOM_HEADER, THEME_CUSTOM_HEADER_VALUE)
            .body(Vec::new())
            .unwrap();
        let get_resp = handle_preferences_theme_request(&get_req, &controller, |m| window_theme = Some(m));
        assert_eq!(get_resp.status(), 200);
        let get_body: serde_json::Value = serde_json::from_slice(get_resp.body()).expect("json body");
        assert_eq!(get_body.get("themeMode").and_then(|v| v.as_str()), Some("system"));
        assert_eq!(
            get_resp.headers().get("Access-Control-Allow-Origin").and_then(|v| v.to_str().ok()),
            Some("http://127.0.0.1:18732")
        );

        // POST sets and persists Dark
        let post_req = tauri::http::Request::builder()
            .method("POST")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header("Origin", "http://127.0.0.1:18732")
            .header(THEME_CUSTOM_HEADER, THEME_CUSTOM_HEADER_VALUE)
            .header("Content-Type", "application/json")
            .body(br#"{"themeMode":"dark"}"#.to_vec())
            .unwrap();
        let post_resp = handle_preferences_theme_request(&post_req, &controller, |m| window_theme = Some(m));
        assert_eq!(post_resp.status(), 200);
        let post_body: serde_json::Value = serde_json::from_slice(post_resp.body()).expect("json body");
        assert_eq!(post_body.get("themeMode").and_then(|v| v.as_str()), Some("dark"));
        assert_eq!(controller.theme_mode(), ThemeMode::Dark);
        assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::Dark);
        assert_eq!(window_theme, Some(ThemeMode::Dark));

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn foreign_and_missing_origin_rejected_leaving_state_unchanged() {
        let (root, controller, paths) = disposable_theme_root("s15-07-theme-origins");
        controller.set_theme_mode(ThemeMode::Dark).expect("set initial dark");
        let mut window_theme = None;

        // Foreign origin POST rejected
        let foreign_req = tauri::http::Request::builder()
            .method("POST")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header("Origin", "http://evil.com")
            .header(THEME_CUSTOM_HEADER, THEME_CUSTOM_HEADER_VALUE)
            .header("Content-Type", "application/json")
            .body(br#"{"themeMode":"light"}"#.to_vec())
            .unwrap();
        let foreign_resp = handle_preferences_theme_request(&foreign_req, &controller, |m| window_theme = Some(m));
        assert_eq!(foreign_resp.status(), 403);
        assert!(foreign_resp.headers().get("Access-Control-Allow-Origin").is_none());
        assert_eq!(controller.theme_mode(), ThemeMode::Dark);
        assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::Dark);
        assert_eq!(window_theme, None);

        // Missing Origin POST rejected
        let missing_req = tauri::http::Request::builder()
            .method("POST")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header(THEME_CUSTOM_HEADER, THEME_CUSTOM_HEADER_VALUE)
            .header("Content-Type", "application/json")
            .body(br#"{"themeMode":"light"}"#.to_vec())
            .unwrap();
        let missing_resp = handle_preferences_theme_request(&missing_req, &controller, |m| window_theme = Some(m));
        assert_eq!(missing_resp.status(), 403);
        assert!(missing_resp.headers().get("Access-Control-Allow-Origin").is_none());
        assert_eq!(controller.theme_mode(), ThemeMode::Dark);
        assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::Dark);
        assert_eq!(window_theme, None);

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn malformed_lookalike_origins_rejected() {
        let (root, controller, paths) = disposable_theme_root("s15-07-theme-lookalike");
        controller.set_theme_mode(ThemeMode::Dark).expect("set dark");

        for lookalike in [
            "http://127.0.0.1:18732.attacker.com",
            "http://projecta-bootstrap.localhost.evil.org",
            "http://attacker.com/127.0.0.1:18732",
            "http://not-projecta-bootstrap.localhost",
            "null",
        ] {
            let req = tauri::http::Request::builder()
                .method("POST")
                .uri("http://projecta-bootstrap.localhost/preferences/theme")
                .header("Origin", lookalike)
                .header(THEME_CUSTOM_HEADER, THEME_CUSTOM_HEADER_VALUE)
                .header("Content-Type", "application/json")
                .body(br#"{"themeMode":"light"}"#.to_vec())
                .unwrap();
            let resp = handle_preferences_theme_request(&req, &controller, |_| {});
            assert_eq!(resp.status(), 403, "lookalike origin {lookalike} must be 403");
            assert_eq!(controller.theme_mode(), ThemeMode::Dark);
            assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::Dark);
        }

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn absent_or_wrong_custom_header_rejected() {
        let (root, controller, paths) = disposable_theme_root("s15-07-theme-headers");
        controller.set_theme_mode(ThemeMode::Dark).expect("set dark");

        // Missing header on POST
        let no_hdr_req = tauri::http::Request::builder()
            .method("POST")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header("Origin", "http://127.0.0.1:18732")
            .header("Content-Type", "application/json")
            .body(br#"{"themeMode":"light"}"#.to_vec())
            .unwrap();
        let no_hdr_resp = handle_preferences_theme_request(&no_hdr_req, &controller, |_| {});
        assert_eq!(no_hdr_resp.status(), 403);
        assert_eq!(controller.theme_mode(), ThemeMode::Dark);
        assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::Dark);

        // Wrong header value on POST
        let wrong_hdr_req = tauri::http::Request::builder()
            .method("POST")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header("Origin", "http://127.0.0.1:18732")
            .header(THEME_CUSTOM_HEADER, "0")
            .header("Content-Type", "application/json")
            .body(br#"{"themeMode":"light"}"#.to_vec())
            .unwrap();
        let wrong_hdr_resp = handle_preferences_theme_request(&wrong_hdr_req, &controller, |_| {});
        assert_eq!(wrong_hdr_resp.status(), 403);
        assert_eq!(controller.theme_mode(), ThemeMode::Dark);

        // Missing header on GET
        let no_hdr_get = tauri::http::Request::builder()
            .method("GET")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header("Origin", "http://127.0.0.1:18732")
            .body(Vec::new())
            .unwrap();
        let no_hdr_get_resp = handle_preferences_theme_request(&no_hdr_get, &controller, |_| {});
        assert_eq!(no_hdr_get_resp.status(), 403);

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn invalid_http_method_rejected_with_405() {
        let (root, controller, paths) = disposable_theme_root("s15-07-theme-methods");
        controller.set_theme_mode(ThemeMode::Dark).expect("set dark");

        for method in ["DELETE", "PUT", "PATCH", "HEAD"] {
            let req = tauri::http::Request::builder()
                .method(method)
                .uri("http://projecta-bootstrap.localhost/preferences/theme")
                .header("Origin", "http://127.0.0.1:18732")
                .header(THEME_CUSTOM_HEADER, THEME_CUSTOM_HEADER_VALUE)
                .body(Vec::new())
                .unwrap();
            let resp = handle_preferences_theme_request(&req, &controller, |_| {});
            assert_eq!(resp.status(), 405, "method {method} must be 405");
            assert_eq!(
                resp.headers().get("Allow").and_then(|v| v.to_str().ok()),
                Some("GET, POST, OPTIONS")
            );
            assert_eq!(controller.theme_mode(), ThemeMode::Dark);
            assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::Dark);
        }

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn options_preflight_grants_only_permitted_origin_and_headers() {
        let (root, controller, _paths) = disposable_theme_root("s15-07-theme-options");

        // Trusted loopback SPA origin
        let req1 = tauri::http::Request::builder()
            .method("OPTIONS")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header("Origin", "http://127.0.0.1:18732")
            .body(Vec::new())
            .unwrap();
        let resp1 = handle_preferences_theme_request(&req1, &controller, |_| {});
        assert_eq!(resp1.status(), 204);
        assert_eq!(
            resp1.headers().get("Access-Control-Allow-Origin").and_then(|v| v.to_str().ok()),
            Some("http://127.0.0.1:18732")
        );
        assert_eq!(
            resp1.headers().get("Access-Control-Allow-Methods").and_then(|v| v.to_str().ok()),
            Some("GET, POST, OPTIONS")
        );
        assert_eq!(
            resp1.headers().get("Access-Control-Allow-Headers").and_then(|v| v.to_str().ok()),
            Some("Content-Type, X-Projecta-Theme-Request")
        );

        // Trusted bootstrap origin
        let req2 = tauri::http::Request::builder()
            .method("OPTIONS")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header("Origin", "http://projecta-bootstrap.localhost")
            .body(Vec::new())
            .unwrap();
        let resp2 = handle_preferences_theme_request(&req2, &controller, |_| {});
        assert_eq!(resp2.status(), 204);
        assert_eq!(
            resp2.headers().get("Access-Control-Allow-Origin").and_then(|v| v.to_str().ok()),
            Some("http://projecta-bootstrap.localhost")
        );

        // Foreign origin OPTIONS rejected with 403
        let req_foreign = tauri::http::Request::builder()
            .method("OPTIONS")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .header("Origin", "http://evil.com")
            .body(Vec::new())
            .unwrap();
        let resp_foreign = handle_preferences_theme_request(&req_foreign, &controller, |_| {});
        assert_eq!(resp_foreign.status(), 403);

        // Missing origin OPTIONS rejected with 403
        let req_missing = tauri::http::Request::builder()
            .method("OPTIONS")
            .uri("http://projecta-bootstrap.localhost/preferences/theme")
            .body(Vec::new())
            .unwrap();
        let resp_missing = handle_preferences_theme_request(&req_missing, &controller, |_| {});
        assert_eq!(resp_missing.status(), 403);

        let _ = std::fs::remove_dir_all(&root);
    }
}
