// Projecta S15-03 desktop entrypoint: bootstrap-first window over an app-owned tree.
//
// App launch is the Start binding; window close is the Stop/Cancel binding.
// First-run provisioning lives in the host/protocol path, not here. Recovery,
// hardening, and packaging remain later Sprint 15 tasks and MUST NOT be added
// to this entrypoint.

fn main() {
    projecta_desktop_lib::run();
}
