// Projecta S15-03 desktop host: bootstrap-first window over an app-owned tree.
//
// App launch is the Start binding; window close is the Stop/Cancel binding.
// First-run, recovery, hardening, and packaging belong to S15-04..S15-09 and
// MUST NOT be added here.

fn main() {
    projecta_desktop_lib::run();
}
