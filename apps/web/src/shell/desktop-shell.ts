/**
 * Desktop-shell affordances.
 *
 * One SPA build is served by the local runtime's loopback API both inside the
 * desktop application's own WebView and in an ordinary browser (development and
 * browser hosting). Only the desktop window can present the bundled
 * workspace-management surface, so the return-to-management action must exist
 * only there — a browser has no such surface and must never render a dead
 * control. The desktop window is the only environment that defines
 * `window.isTauri` (the host's own WebView sets it on every document it
 * creates), which makes it a visibility signal only: the action navigates the
 * same window and grants no authority, and the host registers no Tauri command
 * or capability for it.
 */
declare global {
  interface Window {
    /** Set by the desktop shell's own WebView on every document it creates. */
    isTauri?: boolean;
  }
}

/**
 * Absolute URL of the host's workspace-management surface as WebView2 expresses
 * it: `BOOTSTRAP_SURFACE_URL` in `apps/desktop/src-tauri/src/lifecycle.rs`, the
 * exact origin the host itself navigates to (initial view, readiness
 * transition, post-ready failure, runtime-surface show) and already admits in
 * its navigation guard. Navigating there shows the already-served surface in
 * the same window; it stops, restarts, and reseeds nothing.
 */
export const DESKTOP_MANAGEMENT_SURFACE_URL = "http://projecta-bootstrap.localhost/";
