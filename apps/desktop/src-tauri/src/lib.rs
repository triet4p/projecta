// Projecta S15-02 Tauri host library.
//
// One main window navigates to the externally owned loopback Application API
// origin that serves the compiled React SPA same-origin. No Tauri command is
// registered: the WebView has no native bridge in this slice, so there is no
// capability to scope yet (S15-06 owns the manifest). Navigation outside the
// loopback API origin is refused inside the privileged view; explicit
// external-link handling belongs to S15-07.

use tauri::Url;

/// Fixed loopback host for the externally owned Application API.
const LOOPBACK_HOST: &str = "127.0.0.1";

/// Default Application API port (`PORTS["api"]` in `scripts/projecta_local.py`).
const DEFAULT_API_PORT: u16 = 18732;

/// Resolve the loopback API origin this slice may render.
///
/// Only the port is configurable (via `PROJECTA_S15_02_API_PORT`) so the
/// slice can target an explicitly disposable backend. The host and scheme are
/// fixed: no LAN, hosted, or custom-scheme backend is reachable from here.
fn api_origin() -> String {
    let port: u16 = std::env::var("PROJECTA_S15_02_API_PORT")
        .ok()
        .and_then(|raw| raw.parse::<u16>().ok())
        .filter(|port| *port > 0)
        .unwrap_or(DEFAULT_API_PORT);
    format!("http://{LOOPBACK_HOST}:{port}/")
}

/// Whether the privileged view may navigate to `url`.
///
/// Exactly one origin is allowed: the loopback Application API origin above.
/// Everything else (third-party URLs, foreign loopback ports, `file:` URLs,
/// custom schemes) is refused in this view per the desktop release contract.
fn is_allowed_navigation(url: &Url, api_origin: &str) -> bool {
    if url.scheme() != "http" {
        return false;
    }
    if url.host_str() != Some(LOOPBACK_HOST) {
        return false;
    }
    let origin_port = url.port_or_known_default();
    let expected_port: u16 = api_origin
        .rsplit(':')
        .next()
        .and_then(|tail| tail.trim_end_matches('/').parse::<u16>().ok())
        .unwrap_or(DEFAULT_API_PORT);
    if origin_port != Some(expected_port) {
        return false;
    }
    true
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let origin = api_origin();
    // The privileged main view (declared in tauri.conf.json) renders only
    // the loopback API origin. This plugin refuses any other navigation
    // inside that view; S15-07 owns explicit external-link handling.
    let guard: tauri::plugin::TauriPlugin<tauri::Wry> =
        tauri::plugin::Builder::new("s15-02-navigation-guard")
            .on_navigation(move |_webview, url| is_allowed_navigation(url, &origin))
            .build();
    tauri::Builder::default()
        .plugin(guard)
        .on_window_event(|window, event| {
            // Ordinary close: the slice started no service, so there is
            // nothing owned to stop. Externally owned services keep running;
            // S15-03 owns graceful owned-tree shutdown on app close.
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let _ = window.close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
#[cfg(test)]
mod tests {
    use super::{DEFAULT_API_PORT, LOOPBACK_HOST, api_origin, is_allowed_navigation};

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
