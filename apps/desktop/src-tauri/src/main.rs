// Projecta S15-02 vertical slice: one native window over the live loopback SPA.
//
// The slice owns no supervisor operation, no Tauri command, and no second
// window. The externally started disposable backend owns every service; this
// host only renders `http://127.0.0.1:<api-port>/` and refuses foreign
// navigation inside the privileged view. Start/stop, first-run, recovery,
// hardening, and packaging belong to S15-03..S15-09 and MUST NOT be added here.

fn main() {
    projecta_desktop_lib::run();
}
