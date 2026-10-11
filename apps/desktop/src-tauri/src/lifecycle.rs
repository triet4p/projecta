// Projecta S15-03 lifecycle bridge: app-owned supervisor child + bootstrap-first window.
//
// The desktop owns exactly one supervisor tree: it spawns the existing local
// CLI (`projecta/scripts/projecta_local.py start --no-browser`) as a child
// process, stops it through the existing `stop` subcommand (stdin-pipe-free;
// the supervisor consumes `stop.json`), and navigates the SAME main window
// from the locally bundled bootstrap surface to the loopback SPA on real
// readiness. Second launch refuses via the supervisor lock (no second
// tree/TDB2 writer); no retry loop, no Rust process manager, no new Tauri
// command surface, no hidden background service.

use std::io::Read;
use std::process::{Child, ChildStderr, Command, Stdio};
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use tauri::Url;

/// Fixed loopback host for the owned Application API.
pub const LOOPBACK_HOST: &str = "127.0.0.1";

/// Default Application API port (`PORTS["api"]` in `scripts/projecta_local.py`).
pub const DEFAULT_API_PORT: u16 = 18732;

/// Main window label (declared in `tauri.conf.json`).
pub const MAIN_WINDOW_LABEL: &str = "main";

/// Bootstrap surface scheme (locally bundled, no network fetch).
pub const BOOTSTRAP_SCHEME: &str = "projecta-bootstrap";

/// Cold-start deadline: spawn plus real readiness across the whole owned tree.
/// The supervisor itself gates each service at 90 s; this bound covers a full
/// first-run start without retrying anything.
pub const STARTUP_DEADLINE: Duration = Duration::from_secs(300);

/// Bounded graceful-stop wait for reverse-order shutdown on close/cancel.
pub const STOP_TIMEOUT: Duration = Duration::from_secs(120);

/// Lifecycle states surfaced to the bootstrap page (contract §2.1 subset owned
/// by S15-03; degraded/recovery presentation belongs to S15-05).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LifecycleState {
    Bootstrap,
    Starting,
    Ready,
    Stopped,
    Failed,
    ShutdownFailed,
}

impl LifecycleState {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            LifecycleState::Bootstrap => "bootstrap",
            LifecycleState::Starting => "starting",
            LifecycleState::Ready => "ready",
            LifecycleState::Stopped => "stopped",
            LifecycleState::Failed => "failed",
            LifecycleState::ShutdownFailed => "shutdown-failed",
        }
    }
}

/// Owned supervisor child: the running `projecta_local.py start` manager.
/// Shutdown goes through the existing `stop` subcommand (same script, same
/// roots), which writes the `stop.json` request the supervisor's own loop
/// consumes before its reverse-order shutdown.
pub struct OwnedSupervisor {
    child: Child,
    stderr: Option<ChildStderr>,
    _job: JobGuard,
}

impl OwnedSupervisor {
    /// Spawn the owned supervisor child via the bundled Python interpreter.
    ///
    /// `python_exe` is the bundled `runtime/python/python.exe`,
    /// `launcher_script` is `projecta/scripts/projecta_local.py`, and
    /// `package_root`/`data_root` become `PROJECTA_LAUNCHER_PACKAGE_ROOT` and
    /// `PROJECTA_LAUNCHER_DATA_ROOT`. No WebView secret or foreign credential
    /// is injected here; the supervisor scrubs and composes the service
    /// environment itself (`_clear_inherited_secrets`).
    pub fn spawn(
        python_exe: &std::path::Path,
        launcher_script: &std::path::Path,
        package_root: &std::path::Path,
        data_root: &std::path::Path,
    ) -> std::io::Result<Self> {
        let mut command = Command::new(python_exe);
        command
            .arg(launcher_script)
            .arg("start")
            .arg("--no-browser")
            .env("PROJECTA_LAUNCHER_PACKAGE_ROOT", package_root)
            .env("PROJECTA_LAUNCHER_DATA_ROOT", data_root)
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .env("PYTHONNOUSERSITE", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        {
            // New process group so console Ctrl events on the desktop do not
            // leak into owned services; shutdown stays via `stop.json`.
            const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;
            std::os::windows::process::CommandExt::creation_flags(
                &mut command,
                CREATE_NEW_PROCESS_GROUP,
            );
        }
        let mut child = command.spawn()?;
        let stderr = child.stderr.take();
        let raw_handle = raw_handle_of(&child);
        let job = JobGuard::assign(raw_handle);
        Ok(Self { child, stderr, _job: job })
    }

    /// Owned child PID (diagnostics only; never used to manage foreign PIDs).
    #[must_use]
    pub fn pid(&self) -> u32 {
        self.child.id()
    }

    /// Whether the owned supervisor child is still running.
    pub fn is_running(&mut self) -> bool {
        matches!(self.child.try_wait(), Ok(None))
    }

    /// Wait bounded for the owned child to exit. Returns `true` on exit.
    pub fn wait_exit(&mut self, timeout: Duration) -> bool {
        let deadline = Instant::now() + timeout;
        loop {
            match self.child.try_wait() {
                Ok(Some(_)) => return true,
                Ok(None) => {
                    if Instant::now() >= deadline {
                        return false;
                    }
                    std::thread::sleep(Duration::from_millis(100));
                }
                Err(_) => return false,
            }
        }
    }

    /// Terminate the owned child (last resort only, after graceful stop timed
    /// out) and reap it. Returns `true` once the owned child is reaped.
    pub fn kill_and_reap(&mut self, timeout: Duration) -> bool {
        let _ = self.child.kill();
        self.wait_exit(timeout)
    }

    /// Reap an exited child and extract the supervisor's finite failure code
    /// from its stderr tail (`Projecta Local: <msg> [<CODE>]`). Only call
    /// after the child exited; returns `SUPERVISOR_EXITED` when no code is
    /// found (e.g. killed before printing).
    pub fn reap_failure_code(&mut self) -> String {
        let _ = self.child.wait();
        let mut text = String::new();
        if let Some(mut stderr) = self.stderr.take() {
            let _ = stderr.read_to_string(&mut text);
        }
        extract_failure_code(&text).unwrap_or_else(|| "SUPERVISOR_EXITED".to_string())
    }
}

#[cfg(windows)]
fn raw_handle_of(child: &Child) -> isize {
    use std::os::windows::io::AsRawHandle;
    child.as_raw_handle() as isize
}

#[cfg(not(windows))]
fn raw_handle_of(_child: &Child) -> isize {
    0
}

/// Best-effort Windows Job Object with kill-on-close for the owned supervisor
/// child: on abnormal desktop exit the owned tree cannot orphan. This is a
/// backstop, not a process manager — graceful shutdown always goes through
/// the existing `stop` subcommand first. Failures fall back to no job.
struct JobGuard {
    #[allow(dead_code)]
    handle: isize,
}

impl JobGuard {
    #[cfg(windows)]
    fn assign(process: isize) -> Self {
        let handle = unsafe { create_kill_on_close_job(process) };
        Self {
            handle: handle.unwrap_or(0),
        }
    }

    #[cfg(not(windows))]
    fn assign(_process: isize) -> Self {
        Self { handle: 0 }
    }
}

#[cfg(windows)]
impl Drop for JobGuard {
    fn drop(&mut self) {
        if self.handle != 0 {
            unsafe {
                CloseHandle(self.handle);
            }
        }
    }
}

#[cfg(not(windows))]
impl Drop for JobGuard {
    fn drop(&mut self) {}
}

#[cfg(windows)]
#[repr(C)]
struct JobBasicLimits {
    per_process_time: i64,
    per_job_time: i64,
    limit_flags: u32,
    _pad1: u32,
    min_working_set: usize,
    max_working_set: usize,
    active_process_limit: u32,
    _pad2: u32,
    affinity: usize,
    priority_class: u32,
    scheduling_class: u32,
}

#[cfg(windows)]
#[link(name = "kernel32")]
unsafe extern "system" {
    unsafe fn CreateJobObjectW(attributes: *const u16, name: *const u16) -> isize;
    unsafe fn SetInformationJobObject(
        job: isize,
        class: i32,
        info: *const std::ffi::c_void,
        len: u32,
    ) -> i32;
    unsafe fn AssignProcessToJobObject(job: isize, process: isize) -> i32;
    unsafe fn CloseHandle(handle: isize) -> i32;
}

/// Create a kill-on-close job and assign exactly one owned child process.
/// Returns `None` (no job) on any failure; never touches other processes.
#[cfg(windows)]
unsafe fn create_kill_on_close_job(process: isize) -> Option<isize> {
    const JOB_OBJECT_BASIC_LIMIT_INFORMATION: i32 = 2;
    const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: u32 = 0x0000_2000;
    if process == 0 {
        return None;
    }
    unsafe {
        let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
        if job == 0 {
            return None;
        }
        let mut limits: JobBasicLimits = std::mem::zeroed();
        limits.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let applied = SetInformationJobObject(
            job,
            JOB_OBJECT_BASIC_LIMIT_INFORMATION,
            std::ptr::addr_of!(limits).cast(),
            std::mem::size_of::<JobBasicLimits>() as u32,
        );
        if applied == 0 {
            CloseHandle(job);
            return None;
        }
        if AssignProcessToJobObject(job, process) == 0 {
            CloseHandle(job);
            return None;
        }
        Some(job)
    }
}

/// Extract the trailing `[CODE]` failure token from supervisor stderr.
fn extract_failure_code(stderr: &str) -> Option<String> {
    let open = stderr.rfind('[')?;
    let rest = &stderr[open + 1..];
    let close = rest.find(']')?;
    let code = &rest[..close];
    if code.is_empty()
        || code.len() > 64
        || !code
            .bytes()
            .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || b == b'_')
    {
        return None;
    }
    Some(code.to_string())
}

/// Resolve lifecycle paths from the environment, falling back to the packaged
/// sibling layout next to the running executable.
///
/// - `PROJECTA_DESKTOP_PACKAGE_ROOT` (+ `PROJECTA_LAUNCHER_DATA_ROOT`) points
///   at a staged/bundled tree: `<root>/projecta/scripts/projecta_local.py`
///   plus `runtime/python/python.exe` must both exist.
/// - Otherwise the sibling layout (`runtime/…`, `projecta/…` next to the
///   desktop executable) with the per-user `%LOCALAPPDATA%\Projecta` data root.
#[derive(Debug, Clone)]
pub struct LifecyclePaths {
    pub python_exe: std::path::PathBuf,
    pub launcher_script: std::path::PathBuf,
    pub package_root: std::path::PathBuf,
    pub data_root: std::path::PathBuf,
}

impl LifecyclePaths {
    /// Resolve from env/sibling layout; `None` when no bundled tree exists.
    #[must_use]
    pub fn resolve() -> Option<Self> {
        if let (Some(package_root), Some(data_root)) = (
            std::env::var_os("PROJECTA_DESKTOP_PACKAGE_ROOT").map(std::path::PathBuf::from),
            std::env::var_os("PROJECTA_LAUNCHER_DATA_ROOT").map(std::path::PathBuf::from),
        ) {
            let python_exe = package_root.join("runtime/python/python.exe");
            let launcher_script = package_root.join("projecta/scripts/projecta_local.py");
            if python_exe.is_file() && launcher_script.is_file() {
                return Some(Self {
                    python_exe,
                    launcher_script,
                    package_root,
                    data_root,
                });
            }
            return None;
        }
        let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
        let python_exe = exe_dir.join("runtime/python/python.exe");
        let launcher_script = exe_dir.join("projecta/scripts/projecta_local.py");
        if python_exe.is_file() && launcher_script.is_file() {
            let data_root = std::env::var_os("LOCALAPPDATA")
                .map(std::path::PathBuf::from)
                .map(|base| base.join("Projecta"))?;
            return Some(Self {
                python_exe,
                launcher_script,
                package_root: exe_dir,
                data_root,
            });
        }
        None
    }

    /// Invoke the existing `stop` subcommand against these roots: writes the
    /// `stop.json` request the running supervisor consumes before its own
    /// reverse-order shutdown. Best-effort; the caller still waits on (and,
    /// as a last resort, terminates) only the owned child handle.
    fn request_stop(&self) {
        let mut command = Command::new(&self.python_exe);
        command
            .arg(&self.launcher_script)
            .arg("stop")
            .env("PROJECTA_LAUNCHER_PACKAGE_ROOT", &self.package_root)
            .env("PROJECTA_LAUNCHER_DATA_ROOT", &self.data_root)
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .env("PYTHONNOUSERSITE", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        if let Ok(mut child) = command.spawn() {
            let deadline = Instant::now() + Duration::from_secs(30);
            while matches!(child.try_wait(), Ok(None)) && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(100));
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Readiness outcome for one poll of the owned API (dependency-free:
/// minimal HTTP over `TcpStream`; only status 200 counts).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Readiness {
    Ready,
    NotReady,
    ProbeFailed,
}

/// Poll `GET /health/ready` on the owned loopback API with a short timeout.
///
/// Single attempt, no retry loop: the caller decides cadence and the overall
/// startup deadline. Only HTTP 200 counts as ready; every other status or a
/// transport error is `NotReady`/`ProbeFailed` without parsing the body.
#[must_use]
pub fn poll_api_ready(api_port: u16, timeout: Duration) -> Readiness {
    let address = format!("{LOOPBACK_HOST}:{api_port}");
    let Ok(stream) = std::net::TcpStream::connect_timeout(
        &address.parse().unwrap_or("127.0.0.1:1".parse().unwrap()),
        timeout,
    ) else {
        return Readiness::ProbeFailed;
    };
    let _ = stream.set_read_timeout(Some(timeout));
    let _ = stream.set_write_timeout(Some(timeout));
    let mut stream = stream;
    let request = format!(
        "GET /health/ready HTTP/1.1\r\nHost: {LOOPBACK_HOST}:{api_port}\r\nConnection: close\r\n\r\n"
    );
    if std::io::Write::write_all(&mut stream, request.as_bytes()).is_err() {
        return Readiness::ProbeFailed;
    }
    let mut head = [0u8; 64];
    let mut len = 0;
    while len < head.len() {
        match std::io::Read::read(&mut stream, &mut head[len..len + 1]) {
            Ok(0) => break,
            Ok(n) => {
                len += n;
                if len >= 2 && &head[len - 2..len] == b"\r\n" {
                    break;
                }
                if len >= 15 {
                    break;
                }
            }
            Err(_) => return Readiness::ProbeFailed,
        }
    }
    let status_line = String::from_utf8_lossy(&head[..len]);
    if status_line.starts_with("HTTP/1.1 200") || status_line.starts_with("HTTP/1.0 200") {
        Readiness::Ready
    } else if status_line.starts_with("HTTP/") {
        Readiness::NotReady
    } else {
        Readiness::ProbeFailed
    }
}

/// Resolve the loopback API origin this window may render.
///
/// Only the port is configurable (via `PROJECTA_S15_03_API_PORT`, falling
/// back to the S15-02 name, default `18732`). Host and scheme stay fixed: no
/// LAN, hosted, or custom-scheme backend is reachable from the privileged view.
pub fn api_origin() -> String {
    let port: u16 = std::env::var("PROJECTA_S15_03_API_PORT")
        .ok()
        .and_then(|raw| raw.parse::<u16>().ok())
        .filter(|port| *port > 0)
        .or_else(|| {
            std::env::var("PROJECTA_S15_02_API_PORT")
                .ok()
                .and_then(|raw| raw.parse::<u16>().ok())
                .filter(|port| *port > 0)
        })
        .unwrap_or(DEFAULT_API_PORT);
    format!("http://{LOOPBACK_HOST}:{port}/")
}

/// Bootstrap surface URL (locally bundled, no network fetch).
#[must_use]
#[allow(dead_code)]
pub fn bootstrap_url() -> String {
    format!("{BOOTSTRAP_SCHEME}://localhost/")
}

/// Whether the privileged view may navigate to `url`.
///
/// Exactly two sources are allowed: the locally bundled bootstrap surface
/// (`projecta-bootstrap://localhost/`, host startup only) and the owned
/// loopback API origin. Everything else (third-party URLs, foreign loopback
/// ports, `file:` URLs, other custom schemes) is refused in this view per the
/// desktop release contract.
pub fn is_allowed_navigation(url: &Url, api_origin: &str) -> bool {
    if url.scheme() == BOOTSTRAP_SCHEME {
        return url.host_str() == Some("localhost");
    }
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

/// Render the bootstrap page for the current lifecycle snapshot: window
/// chrome plus Start/Stop/diagnostics controls only. No API dependency exists
/// in this state; S15-04 owns workspace provisioning UI and S15-05 owns the
/// full state/error surface and explicit control wiring — app launch is the
/// Start binding and window close is the Stop/Cancel binding in this slice.
/// Content is sanitized: state, finite failure code, owned PID, and API origin
/// only — never secrets, keys, or service output.
#[must_use]
pub fn render_bootstrap(
    state: LifecycleState,
    failure_code: Option<&str>,
    supervisor_pid: Option<u32>,
    api_origin: &str,
) -> String {
    let refresh = if state == LifecycleState::Starting {
        "<meta http-equiv=\"refresh\" content=\"2\">"
    } else {
        ""
    };
    let diagnostics = match (state, failure_code, supervisor_pid) {
        (LifecycleState::Failed, Some(code), _) => format!(
            "Startup failed [{code}]. No second service tree was started; data was retained. Close the window, or resolve the cause and relaunch."
        ),
        (LifecycleState::Failed, None, _) => {
            "Startup failed. No second service tree was started; data was retained.".to_string()
        }
        (LifecycleState::Starting, _, Some(pid)) => format!(
            "Starting owned services (supervisor {pid}); waiting for {api_origin}health/ready. Closing the window cancels startup and stops owned services only."
        ),
        (LifecycleState::Starting, _, None) => {
            "Starting owned services; waiting for backend readiness.".to_string()
        }
        (LifecycleState::Ready, _, _) => {
            "Backend ready; opening the workspace.".to_string()
        }
        (LifecycleState::ShutdownFailed, Some(code), _) => format!(
            "Graceful stop did not complete [{code}]. Owned processes were terminated; data was retained."
        ),
        (LifecycleState::ShutdownFailed, None, _) => {
            "Graceful stop did not complete. Owned processes were terminated; data was retained."
                .to_string()
        }
        _ => "Local runtime bootstrap. No service started yet.".to_string(),
    };
    format!(
        r#"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
{refresh}
<title>Projecta</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
#state {{ font-weight: bold; }}
#diagnostics {{ white-space: pre-wrap; margin-top: 1rem; color: #444; }}
button {{ margin-right: .5rem; padding: .4rem 1rem; }}
</style>
</head>
<body>
<h1>Projecta</h1>
<p>State: <span id="state" data-testid="lifecycle-state">{}</span></p>
<button id="start" data-testid="lifecycle-start" disabled>Start</button>
<button id="stop" data-testid="lifecycle-stop" disabled>Stop</button>
<pre id="diagnostics" data-testid="lifecycle-diagnostics">{diagnostics}</pre>
</body>
</html>"#,
        state.as_str()
    )
}

/// App-owned lifecycle controller: spawn/stop exactly one supervisor child,
/// poll readiness, and track the window state for bootstrap→SPA navigation.
/// Interior mutability: the blocking `cold_start` runs on a worker thread
/// while window-close handling signals cancellation from the event loop.
pub struct LifecycleController {
    paths: Option<LifecyclePaths>,
    api_port: u16,
    state: Mutex<LifecycleState>,
    failure_code: Mutex<Option<String>>,
    supervisor: Mutex<Option<OwnedSupervisor>>,
    cancel: AtomicBool,
    startup_handle: Mutex<Option<JoinHandle<bool>>>,
}

impl LifecycleController {
    #[must_use]
    pub fn new(paths: Option<LifecyclePaths>, api_port: u16) -> Self {
        Self {
            paths,
            api_port,
            state: Mutex::new(LifecycleState::Bootstrap),
            failure_code: Mutex::new(None),
            supervisor: Mutex::new(None),
            cancel: AtomicBool::new(false),
            startup_handle: Mutex::new(None),
        }
    }

    #[must_use]
    pub fn state(&self) -> LifecycleState {
        *self.state.lock().unwrap_or_else(|e| e.into_inner())
    }

    #[must_use]
    pub fn failure_code(&self) -> Option<String> {
        self.failure_code
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .clone()
    }

    #[must_use]
    #[allow(dead_code)]
    pub fn api_port(&self) -> u16 {
        self.api_port
    }

    #[must_use]
    pub fn supervisor_pid(&self) -> Option<u32> {
        self.supervisor
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .as_ref()
            .map(OwnedSupervisor::pid)
    }

    /// Whether an owned supervisor child handle exists (regardless of liveness).
    #[must_use]
    pub fn has_supervisor(&self) -> bool {
        self.supervisor
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .is_some()
    }

    fn set_state(&self, state: LifecycleState, failure_code: Option<String>) {
        *self.state.lock().unwrap_or_else(|e| e.into_inner()) = state;
        *self
            .failure_code
            .lock()
            .unwrap_or_else(|e| e.into_inner()) = failure_code;
    }

    /// Snapshot for the bootstrap renderer: (state, failure code, owned PID).
    pub fn snapshot(&self) -> (LifecycleState, Option<String>, Option<u32>) {
        (self.state(), self.failure_code(), self.supervisor_pid())
    }

    /// Stash the worker-thread handle running `cold_start` (setup path).
    pub fn set_startup_handle(&self, handle: JoinHandle<bool>) {
        *self.startup_handle.lock().unwrap_or_else(|e| e.into_inner()) = Some(handle);
    }

    /// Take the worker-thread handle (close path joins it exactly once).
    pub fn take_startup_handle(&self) -> Option<JoinHandle<bool>> {
        self.startup_handle
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .take()
    }

    /// Signal cancellation of an in-flight startup (close-during-starting).
    pub fn request_cancel(&self) {
        self.cancel.store(true, Ordering::SeqCst);
    }

    #[must_use]
    pub fn cancel_requested(&self) -> bool {
        self.cancel.load(Ordering::SeqCst)
    }

    /// Cold start: spawn the owned supervisor child and wait for real API
    /// readiness. Single attempt, no retry: failure records the finite code
    /// (`RUNTIME_ALREADY_ACTIVE` on lock refusal, `SERVICE_READINESS_TIMEOUT`
    /// on deadline, `SUPERVISOR_EXITED`/spawn codes otherwise) and stops any
    /// owned child started so far. Cancellation stops the owned tree and
    /// reports `stopped`.
    pub fn cold_start(&self) -> bool {
        if self.has_supervisor() {
            self.set_state(
                LifecycleState::Failed,
                Some("ALREADY_STARTED".to_string()),
            );
            return false;
        }
        let Some(paths) = self.paths.clone() else {
            self.set_state(
                LifecycleState::Failed,
                Some("RUNTIME_PACKAGE_MISSING".to_string()),
            );
            return false;
        };
        self.set_state(LifecycleState::Starting, None);
        let child = match OwnedSupervisor::spawn(
            &paths.python_exe,
            &paths.launcher_script,
            &paths.package_root,
            &paths.data_root,
        ) {
            Ok(child) => child,
            Err(_) => {
                self.set_state(
                    LifecycleState::Failed,
                    Some("SUPERVISOR_SPAWN_FAILED".to_string()),
                );
                return false;
            }
        };
        *self.supervisor.lock().unwrap_or_else(|e| e.into_inner()) = Some(child);
        // Give the supervisor a moment to claim its lock: an immediate exit
        // means it failed closed (second instance, port collision, or package
        // fault) and its finite code is in its stderr tail.
        std::thread::sleep(Duration::from_millis(1500));
        let early_exit = self
            .supervisor
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .as_mut()
            .is_none_or(|s| !s.is_running());
        if early_exit {
            let code = self
                .supervisor
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .take()
                .map(|mut s| s.reap_failure_code());
            self.set_state(LifecycleState::Failed, code);
            return false;
        }
        // Wait for real readiness, checking cancellation every poll. No
        // automatic recovery or restart on failure.
        let started = Instant::now();
        while started.elapsed() < STARTUP_DEADLINE {
            if self.cancel_requested() {
                self.cancel_start();
                return false;
            }
            if poll_api_ready(self.api_port, Duration::from_secs(2)) == Readiness::Ready {
                // The tree may still be pre-supervision; confirm the manager
                // holds the lock by requiring the child alive at ready.
                let alive = self
                    .supervisor
                    .lock()
                    .unwrap_or_else(|e| e.into_inner())
                    .as_mut()
                    .is_some_and(OwnedSupervisor::is_running);
                if alive {
                    self.set_state(LifecycleState::Ready, None);
                    return true;
                }
                break;
            }
            std::thread::sleep(Duration::from_millis(500));
        }
        if self.cancel_requested() {
            self.cancel_start();
            return false;
        }
        // Startup deadline passed or the supervisor exited mid-start:
        // cancel — stop only the owned child, release locks/ports, retain data.
        let still_running = self
            .supervisor
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .as_mut()
            .is_some_and(OwnedSupervisor::is_running);
        if still_running {
            self.stop_owned(STOP_TIMEOUT);
            self.set_state(
                LifecycleState::Failed,
                Some("SERVICE_READINESS_TIMEOUT".to_string()),
            );
        } else {
            let code = self
                .supervisor
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .take()
                .map(|mut s| s.reap_failure_code());
            self.set_state(LifecycleState::Failed, code);
        }
        false
    }

    /// Cancel a `starting` tree: promptly terminate the owned supervisor child
    /// (still inside its ordered start; `stop.json` is only consumed once
    /// supervising), letting its Job Object backstop reap the partially
    /// started owned tree. Releases locks/ports, retains data.
    pub fn cancel_start(&self) {
        self.stop_owned_prompt();
        if self.state() == LifecycleState::Starting {
            self.write_stopped_status();
            self.set_state(LifecycleState::Stopped, None);
        }
    }

    /// Best-effort final status write after a prompt mid-start cancel killed
    /// the owned supervisor before it could publish its own terminal state.
    /// Preserves the supervisor's own `runtimeId`/`managerPid` (state flip to
    /// `stopped`, services cleared); never touches foreign state.
    fn write_stopped_status(&self) {
        let path = self.paths.clone().map(|p| p.data_root.join("state/runtime.json"));
        let Some(path) = path else { return };
        let mut document = std::fs::read_to_string(&path)
            .ok()
            .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
            .filter(|value| value.is_object())
            .unwrap_or_else(|| serde_json::json!({}));
        if let Some(object) = document.as_object_mut() {
            object.insert("state".to_string(), serde_json::json!("stopped"));
            object.insert("services".to_string(), serde_json::json!({}));
            object.insert("processes".to_string(), serde_json::json!({}));
            object.insert("url".to_string(), serde_json::Value::Null);
            object.remove("failureCode");
            object.remove("failedService");
        }
        if let Ok(text) = serde_json::to_string_pretty(&document) {
            if let Some(parent) = path.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            let tmp = path.with_extension("json.tmp");
            if std::fs::write(&tmp, text.as_bytes()).is_ok() {
                let _ = std::fs::rename(&tmp, &path);
            }
        }
    }

    /// Ordinary app close: graceful reverse-order stop of owned children only
    /// (via the existing `stop` subcommand), then release locks/ports and
    /// retain all data. Returns `true` when no owned child remains; on
    /// timeout records `shutdown-failed` without touching foreign processes.
    pub fn shutdown(&self) -> bool {
        self.stop_owned(STOP_TIMEOUT);
        if self.has_supervisor() {
            self.set_state(
                LifecycleState::ShutdownFailed,
                Some("GRACEFUL_STOP_TIMEOUT".to_string()),
            );
            return false;
        }
        if self.state() != LifecycleState::Stopped {
            let failure = self.failure_code();
            let keep = matches!(
                self.state(),
                LifecycleState::Failed | LifecycleState::ShutdownFailed
            )
            .then_some(failure)
            .flatten();
            self.set_state(LifecycleState::Stopped, keep);
        }
        true
    }

    /// Stop the owned supervisor child: graceful `stop` request first with a
    /// bounded wait, owned-child termination as the last resort. Foreign
    /// processes are never signalled.
    ///
    /// When `prompt` is set (cancel during `starting`), the owned supervisor
    /// child is terminated promptly instead of waiting out the full graceful
    /// bound: mid-start the supervisor is still inside its ordered start and
    /// only consumes `stop.json` once supervising, so a graceful request
    /// cannot complete until the tree it is meant to cancel finishes
    /// starting. Termination covers exactly the owned child handle; the
    /// Windows Job Object backstop reaps its own children on abnormal
    /// manager exit, and the per-user lock releases with the manager.
    fn stop_owned(&self, timeout: Duration) {
        self.stop_owned_inner(timeout, false);
    }

    fn stop_owned_prompt(&self) {
        self.stop_owned_inner(Duration::from_secs(30), true);
    }

    fn stop_owned_inner(&self, timeout: Duration, prompt: bool) {
        let paths = self.paths.clone();
        let mut guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
        let Some(supervisor) = guard.as_mut() else {
            return;
        };
        if !supervisor.is_running() {
            guard.take();
            return;
        }
        if prompt {
            // Mid-start cancel: terminate the owned supervisor child promptly.
            // Its Job Object backstop reaps the partially started owned tree;
            // foreign processes are never touched. Bounded reap below.
            if supervisor.kill_and_reap(Duration::from_secs(30)) {
                guard.take();
            }
            return;
        }
        if let Some(paths) = paths {
            drop(guard);
            paths.request_stop();
            guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
            let Some(supervisor) = guard.as_mut() else {
                return;
            };
            if supervisor.wait_exit(timeout) {
                guard.take();
                return;
            }
            // Last resort: terminate the owned child only. Its Job Object
            // backstop reaps its own children on abnormal manager exit.
            if supervisor.kill_and_reap(Duration::from_secs(10)) {
                let still_there = guard.take();
                drop(still_there);
                // Graceful stop genuinely did not complete in bound; the
                // caller records the outcome state.
                drop(guard);
                self.set_state(
                    self.state(),
                    Some("GRACEFUL_STOP_TIMEOUT".to_string()),
                );
                return;
            }
        } else if supervisor.kill_and_reap(Duration::from_secs(10)) {
            guard.take();
        }
    }
}
#[cfg(test)]
mod lifecycle_tests {
    use super::{
        BOOTSTRAP_SCHEME, DEFAULT_API_PORT, LOOPBACK_HOST, LifecycleController, LifecyclePaths,
        LifecycleState, Readiness, api_origin, bootstrap_url, extract_failure_code,
        is_allowed_navigation, poll_api_ready, render_bootstrap,
    };

    #[test]
    fn api_origin_stays_loopback_http() {
        let origin = api_origin();
        assert!(
            origin.starts_with(&format!("http://{LOOPBACK_HOST}:")),
            "unexpected API origin: {origin}"
        );
        assert!(!origin.contains("https://"), "lifecycle must not upgrade to TLS");
    }

    #[test]
    fn default_port_matches_launcher_api_port() {
        assert_eq!(DEFAULT_API_PORT, 18732);
    }

    #[test]
    fn navigation_allows_bootstrap_and_owned_origin_only() {
        let origin = format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/");
        let allowed: url::Url = origin.parse().expect("valid origin");
        assert!(is_allowed_navigation(&allowed, &origin));
        let bootstrap: url::Url = bootstrap_url().parse().expect("valid bootstrap URL");
        assert_eq!(bootstrap.scheme(), BOOTSTRAP_SCHEME);
        assert!(is_allowed_navigation(&bootstrap, &origin));
        for raw in [
            "https://example.test/",
            "http://example.test/",
            "http://127.0.0.1:18080/",
            "http://localhost:18732/",
            "file:///C:/Windows/win.ini",
            "tauri://localhost/",
            "projecta-bootstrap://other/",
        ] {
            let url: url::Url = raw.parse().expect("valid URL");
            assert!(
                !is_allowed_navigation(&url, &origin),
                "must refuse navigation to {raw}"
            );
        }
    }

    #[test]
    fn lifecycle_states_cover_contract_transitions() {
        assert_eq!(LifecycleState::Bootstrap.as_str(), "bootstrap");
        assert_eq!(LifecycleState::Starting.as_str(), "starting");
        assert_eq!(LifecycleState::Ready.as_str(), "ready");
        assert_eq!(LifecycleState::Stopped.as_str(), "stopped");
        assert_eq!(LifecycleState::Failed.as_str(), "failed");
        assert_eq!(LifecycleState::ShutdownFailed.as_str(), "shutdown-failed");
    }

    #[test]
    fn controller_without_package_fails_closed() {
        let controller = LifecycleController::new(None, DEFAULT_API_PORT);
        assert!(!controller.cold_start());
        assert_eq!(controller.state(), LifecycleState::Failed);
        assert_eq!(
            controller.failure_code().as_deref(),
            Some("RUNTIME_PACKAGE_MISSING")
        );
        assert!(!controller.has_supervisor());
    }

    #[test]
    fn shutdown_without_child_is_stopped() {
        let controller = LifecycleController::new(None, DEFAULT_API_PORT);
        assert!(controller.shutdown());
        assert_eq!(controller.state(), LifecycleState::Stopped);
    }

    #[test]
    fn bootstrap_page_exposes_lifecycle_controls() {
        let html = render_bootstrap(
            LifecycleState::Starting,
            None,
            Some(1234),
            &format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/"),
        );
        assert!(html.contains("data-testid=\"lifecycle-state\""));
        assert!(html.contains("data-testid=\"lifecycle-start\""));
        assert!(html.contains("data-testid=\"lifecycle-stop\""));
        assert!(html.contains("data-testid=\"lifecycle-diagnostics\""));
        assert!(html.contains("starting"));
        // Starting state auto-refreshes the view only (no service retry).
        assert!(html.contains("http-equiv=\"refresh\""));
        let failed = render_bootstrap(
            LifecycleState::Failed,
            Some("RUNTIME_ALREADY_ACTIVE"),
            None,
            &format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/"),
        );
        assert!(failed.contains("RUNTIME_ALREADY_ACTIVE"));
        assert!(!failed.contains("http-equiv=\"refresh\""));
    }

    #[test]
    fn failure_code_extraction_reads_supervisor_stderr() {
        assert_eq!(
            extract_failure_code("Projecta Local: already running [RUNTIME_ALREADY_ACTIVE]\n"),
            Some("RUNTIME_ALREADY_ACTIVE".to_string())
        );
        assert_eq!(
            extract_failure_code("boom [PORT_IN_USE]\n"),
            Some("PORT_IN_USE".to_string())
        );
        assert_eq!(extract_failure_code("no code here\n"), None);
        assert_eq!(extract_failure_code("lower [not_a_code]\n"), None);
    }

    #[test]
    fn readiness_probe_fails_closed_on_closed_port() {
        // Bind an ephemeral port, drop it, and probe: nothing listens, so the
        // probe must not report ready (refused vs timeout both count).
        let listener =
            std::net::TcpListener::bind("127.0.0.1:0").expect("ephemeral loopback port");
        let port = listener.local_addr().expect("local addr").port();
        drop(listener);
        let outcome = poll_api_ready(port, std::time::Duration::from_secs(2));
        assert!(
            outcome == Readiness::ProbeFailed || outcome == Readiness::NotReady,
            "closed port must not probe ready, got {outcome:?}"
        );
    }

    #[test]
    fn second_cold_start_while_owned_refuses_without_second_child() {
        // Boundary: starting twice must not create a second supervisor tree.
        // Feed an invalid package root (missing interpreter) so the first
        // start fails fast, then verify a repeated start is still refused.
        let paths = LifecyclePaths {
            python_exe: std::path::PathBuf::from("C:/nonexistent/python.exe"),
            launcher_script: std::path::PathBuf::from("C:/nonexistent/projecta_local.py"),
            package_root: std::path::PathBuf::from("C:/nonexistent"),
            data_root: std::path::PathBuf::from("C:/nonexistent-data"),
        };
        let controller = LifecycleController::new(Some(paths), DEFAULT_API_PORT);
        assert!(!controller.cold_start());
        assert_eq!(controller.state(), LifecycleState::Failed);
        assert_eq!(
            controller.failure_code().as_deref(),
            Some("SUPERVISOR_SPAWN_FAILED")
        );
        // The failed controller holds no child: shutdown releases nothing and
        // preserves the stopped state without touching foreign processes.
        assert!(!controller.has_supervisor());
        assert!(controller.shutdown());
        assert_eq!(controller.state(), LifecycleState::Stopped);
    }

    #[test]
    fn shutdown_failed_state_preserves_failure_code() {
        // Boundary: `shutdown` on a failed controller keeps the finite code
        // (no silent success screen) while releasing the owned handle set.
        let controller = LifecycleController::new(None, DEFAULT_API_PORT);
        assert!(!controller.cold_start());
        assert_eq!(controller.failure_code().as_deref(), Some("RUNTIME_PACKAGE_MISSING"));
        assert!(controller.shutdown());
        assert_eq!(controller.state(), LifecycleState::Stopped);
    }
}
