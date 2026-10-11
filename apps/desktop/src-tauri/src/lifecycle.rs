// Projecta S15-03/05 lifecycle bridge: app-owned supervisor child + same-window
// runtime-control surface.
//
// The desktop owns exactly one supervisor tree: it spawns the existing local
// CLI (`projecta/scripts/projecta_local.py start --no-browser`) as a child
// process, stops it through the existing `stop` subcommand (stdin-pipe-free;
// the supervisor consumes `stop.json`), and navigates the SAME main window
// between the locally bundled bootstrap surface and the loopback SPA on real
// readiness. Second launch refuses via the supervisor lock (no second
// tree/TDB2 writer); no retry loop, no Rust process manager, no new Tauri
// command surface, no hidden background service.
//
// S15-05 adds the runtime-control surface in that same window: the durable
// lifecycle states of contract §2.1 (`bootstrap`, `starting`, `ready`,
// `degraded`, `stopped`, `failed`, `shutdown-failed`) are presented with
// Start/Stop controls, bounded user-initiated recovery, and sanitized
// diagnostics that carry the supervisor's own finite failure code and failing
// service name (read from the owned `state/runtime.json` document the Python
// `status` command already reads). No state is inferred, no failure is
// suppressed, and no automatic recovery is performed by this layer.

use std::io::Read;
use std::process::{Child, ChildStderr, Command, Stdio};
use std::sync::Arc;
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

/// Bounded wait for the surface Stop control while the owned manager performs
/// its own reverse-order shutdown. This bound only exceeds the manager's own
/// per-service stop timeouts so a healthy graceful shutdown is never cut short
/// by the surface; it is never a retry, and the manager stays authoritative for
/// the `shutdown-failed` explicit stop retry.
pub const STOP_REQUEST_BOUND: Duration = Duration::from_secs(300);

/// How often the stop path re-reads the owned status document while waiting for
/// the manager's reverse-order shutdown.
const STOP_STATUS_POLL: Duration = Duration::from_millis(500);

/// The fixed loopback service ports, mirroring `PORTS` in
/// `scripts/projecta_local.py`. Nothing here selects or falls back to another
/// port: the list exists only so the surface can name the occupied port when
/// the supervisor itself refuses with `PORT_IN_USE`.
pub const FIXED_SERVICE_PORTS: [(&str, u16); 4] = [
    ("postgres", 15432),
    ("fuseki", 18303),
    ("semanticCore", 18080),
    ("api", 18732),
];

/// Absolute URL of the bundled lifecycle surface as WebView2 expresses it. The
/// platform cannot navigate directly to a non-standard scheme, so every
/// lifecycle navigation (form actions, meta refresh, menu "show" action) uses
/// this exact workaround origin, which `is_allowed_navigation` already permits
/// on its default port without credentials.
pub const BOOTSTRAP_SURFACE_URL: &str = "http://projecta-bootstrap.localhost/";

/// Sanitized failure record: the supervisor's own finite code, the failing
/// service name when the supervisor reports one, and an optional short detail
/// line (currently only the occupied-port observation for `PORT_IN_USE`). No
/// raw stderr, log line, path, or secret is ever stored or rendered.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FailureRecord {
    pub code: String,
    pub service: Option<String>,
    pub detail: Option<String>,
}

impl FailureRecord {
    /// Build a record from a supervisor code plus optional failing service. A
    /// `PORT_IN_USE` code additionally records which fixed loopback ports are
    /// occupied at observation time, so the surface names the dependency the
    /// supervisor refused to replace.
    #[must_use]
    pub fn new(code: String, service: Option<String>) -> Self {
        let detail = if code == "PORT_IN_USE" {
            let occupied = occupied_fixed_loopback_ports();
            (!occupied.is_empty()).then(|| {
                occupied
                    .iter()
                    .map(|(name, port)| format!("{name} on port {port}"))
                    .collect::<Vec<_>>()
                    .join(", ")
            })
        } else {
            None
        };
        Self { code, service, detail }
    }
}

/// Probe the fixed loopback ports read-only (bind and immediately release) and
/// report which are occupied. Never keeps a listener, never signals another
/// process, and never chooses a different port.
#[must_use]
pub fn occupied_fixed_loopback_ports() -> Vec<(&'static str, u16)> {
    FIXED_SERVICE_PORTS
        .iter()
        .filter(|(_, port)| std::net::TcpListener::bind((LOOPBACK_HOST, *port)).is_err())
        .map(|(name, port)| (*name, *port))
        .collect()
}

/// Lifecycle states surfaced to the same window (contract §2.1).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LifecycleState {
    Bootstrap,
    Starting,
    Ready,
    Degraded,
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
            LifecycleState::Degraded => "degraded",
            LifecycleState::Stopped => "stopped",
            LifecycleState::Failed => "failed",
            LifecycleState::ShutdownFailed => "shutdown-failed",
        }
    }
}

/// Live snapshot rendered by the lifecycle surface. Sanitized by construction:
/// state, finite failure record, owned supervisor PID, and the stop/start
/// in-flight flags that decide whether the view refreshes.
#[derive(Debug, Clone)]
pub struct LifecycleSnapshot {
    pub state: LifecycleState,
    pub failure: Option<FailureRecord>,
    pub supervisor_pid: Option<u32>,
    pub stop_pending: bool,
    pub start_pending: bool,
}

/// Outcome of a surface Stop: either the owned tree reached `stopped`, or the
/// manager is alive and waiting for the contract's explicit stop retry.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StopOutcome {
    Stopped,
    ShutdownFailed,
}

/// Which runtime action a native menu item maps to. Pure mapping so the menu
/// wiring is testable without input automation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RuntimeMenuAction {
    Start,
    Stop,
    ShowControls,
    None,
}

/// Map a native menu item id to its runtime action. The ids are the ones the
/// host registers; anything else is ignored.
#[must_use]
pub fn runtime_menu_action(id: &str) -> RuntimeMenuAction {
    match id {
        "runtime-start" => RuntimeMenuAction::Start,
        "runtime-stop" => RuntimeMenuAction::Stop,
        "runtime-show" => RuntimeMenuAction::ShowControls,
        _ => RuntimeMenuAction::None,
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
    is_finite_code(code).then(|| code.to_string())
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

    /// Workspace registry marker inside the data root: `config/local-runtime.json`.
    ///
    /// The launcher writes this file exactly once, on a fresh data directory
    /// only, and refuses to overwrite it. Its absence is therefore the single
    /// authoritative first-run signal; its presence means an existing workspace
    /// that MUST NOT be reseeded, overwritten, or re-provisioned.
    #[must_use]
    pub fn workspace_config_path(&self) -> std::path::PathBuf {
        self.data_root.join("config/local-runtime.json")
    }

    /// Whether the data root already holds a provisioned workspace.
    #[must_use]
    pub fn has_workspace(&self) -> bool {
        self.workspace_config_path().is_file()
    }

    /// Invoke the existing `provision` subcommand against these roots: the
    /// workspace-initialization half of installation only. It reuses the
    /// audited Python name validation, the generated project, the fixed
    /// `local-operator` actor, and DPAPI CurrentUser protection of the runtime
    /// secrets, and it NEVER performs OS installation (no package copy, no
    /// Start-Menu shortcut, no HKCU write) — so provisioning from the main
    /// window cannot install anything regardless of frozen or unfrozen
    /// execution. Single attempt, bounded wait, no retry loop.
    ///
    /// `stdout` is returned sanitized (finite status text) and `stderr` is used
    /// only to extract the launcher's trailing `[CODE]` token; neither is ever
    /// surfaced raw to the WebView.
    pub fn provision_workspace(&self, workspace_name: &str) -> Result<(), String> {
        let mut command = Command::new(&self.python_exe);
        command
            .arg(&self.launcher_script)
            .arg("provision")
            .arg("--workspace-name")
            .arg(workspace_name)
            .env("PROJECTA_LAUNCHER_PACKAGE_ROOT", &self.package_root)
            .env("PROJECTA_LAUNCHER_DATA_ROOT", &self.data_root)
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .env("PYTHONNOUSERSITE", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let Ok(mut child) = command.spawn() else {
            return Err("PROVISION_SPAWN_FAILED".to_string());
        };
        let deadline = Instant::now() + Duration::from_secs(120);
        loop {
            match child.try_wait() {
                Ok(Some(_)) => {
                    let Ok(output) = child.wait_with_output() else {
                        return Err("PROVISION_OUTPUT_UNREADABLE".to_string());
                    };
                    if output.status.success() {
                        return Ok(());
                    }
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    return Err(extract_failure_code(&stderr).unwrap_or_else(|| {
                        if stderr.contains("invalid choice") || stderr.contains("COMMAND_INVALID") {
                            // A packaged launcher built before this subcommand
                            // existed cannot provision in-window; surface a
                            // finite, actionable code rather than a generic one.
                            "FIRST_RUN_UNSUPPORTED_PACKAGE".to_string()
                        } else {
                            "PROVISION_FAILED".to_string()
                        }
                    }));
                }
                Ok(None) => {
                    if Instant::now() >= deadline {
                        let _ = child.kill();
                        let _ = child.wait();
                        return Err("PROVISION_TIMEOUT".to_string());
                    }
                    std::thread::sleep(Duration::from_millis(100));
                }
                Err(_) => {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err("PROVISION_WAIT_FAILED".to_string());
                }
            }
        }
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

    /// Read the owned manager's status document (`state/runtime.json`) — the
    /// same document the existing `status` subcommand and the launcher log
    /// already expose — and return only its sanitized lifecycle view.
    ///
    /// This is a read of task-owned state written by the owned manager: no
    /// foreign state is inspected, no file is written, and every field is
    /// validated against the finite sets the supervisor itself uses (`state`
    /// words, `failureCode` token shape, `failedService` service names), so an
    /// unexpected document degrades to `None` instead of rendering arbitrary
    /// content.
    #[must_use]
    pub fn read_runtime_status(&self) -> Option<RuntimeStatusSnapshot> {
        let path = self.data_root.join("state/runtime.json");
        let text = std::fs::read_to_string(&path).ok()?;
        let document: serde_json::Value = serde_json::from_str(&text).ok()?;
        let object = document.as_object()?;
        let state = match object.get("state").and_then(serde_json::Value::as_str) {
            Some("starting") | Some("ready") | Some("stopped") | Some("failed")
            | Some("shutdown-failed") => object["state"].as_str().map(str::to_string),
            _ => None,
        };
        let failure = match object.get("failureCode").and_then(serde_json::Value::as_str) {
            Some(code) if is_finite_code(code) => {
                let service = object
                    .get("failedService")
                    .and_then(serde_json::Value::as_str)
                    .filter(|service| is_service_name(service))
                    .map(str::to_string);
                Some(FailureRecord::new(code.to_string(), service))
            }
            _ => None,
        };
        Some(RuntimeStatusSnapshot { state, failure })
    }
}

/// Sanitized lifecycle view of the owned manager's status document.
#[derive(Debug, Clone)]
pub struct RuntimeStatusSnapshot {
    pub state: Option<String>,
    pub failure: Option<FailureRecord>,
}

/// Whether a value is a finite failure-code token: uppercase ASCII letters,
/// digits, and underscores only, at most 64 characters. Everything else is
/// refused so the surface can never render arbitrary document content.
#[must_use]
pub fn is_finite_code(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_uppercase() || byte.is_ascii_digit() || byte == b'_')
}

/// Whether a value is one of the owned service names the supervisor reports as
/// `failedService`.
#[must_use]
pub fn is_service_name(value: &str) -> bool {
    FIXED_SERVICE_PORTS
        .iter()
        .any(|(name, _)| *name == value)
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

/// Host prefix WebView2 uses for the bundled bootstrap protocol.
///
/// WebView2 cannot navigate directly to a non-standard scheme, so wry
/// rewrites `projecta-bootstrap://localhost/…` to the workaround URI
/// `http://projecta-bootstrap.localhost/…` and reverts it before the custom
/// protocol handler sees the request. Consults
/// `wry::custom_protocol_workaround`.
pub const BOOTSTRAP_WORKAROUND_HOST: &str = "projecta-bootstrap.localhost";

/// Whether the privileged view may navigate to `url`.
///
/// Exactly two sources are allowed: the locally bundled bootstrap surface
/// (`projecta-bootstrap://localhost/`, host startup only) and the owned
/// loopback API origin. The bootstrap surface is additionally reachable through
/// WebView2's workaround host (`http://projecta-bootstrap.localhost/…`), because
/// that is how the platform expresses a navigation to a non-standard scheme.
/// Everything else (third-party URLs, foreign loopback ports, `file:` URLs,
/// other custom schemes) is refused in this view per the desktop release
/// contract.
pub fn is_allowed_navigation(url: &Url, api_origin: &str) -> bool {
    if url.scheme() == BOOTSTRAP_SCHEME {
        return url.host_str() == Some("localhost")
            && url.port().is_none()
            && url.username().is_empty()
            && url.password().is_none();
    }
    // WebView2 rewrites the bundled protocol as this exact HTTP origin; keep
    // it limited to its default port and reject credential-bearing URLs.
    if url.scheme() == "http" && url.host_str() == Some(BOOTSTRAP_WORKAROUND_HOST) {
        return url.port_or_known_default() == Some(80)
            && url.username().is_empty()
            && url.password().is_none();
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

/// Render the lifecycle surface for the current snapshot in the SAME main
/// window: window chrome plus Start/Stop controls, the finite failure record,
/// and sanitized diagnostics. No API dependency exists in this state; the
/// separate S15-04 first-run form handles workspace provisioning.
///
/// Controls are plain form submissions to the bundled surface (no script, no
/// Tauri command, no capability): Start maps to the existing `start` operation
/// with a single bounded attempt and Stop maps to the existing `stop`
/// operation. Both are disabled where the action cannot apply (Start while
/// starting/ready; Stop with nothing to stop) so the surface never offers an
/// empty success path.
///
/// Content is sanitized by construction: state, finite failure code, failing
/// service name, owned PID, and at most the occupied-port observation. No
/// secret, key, credential, raw service output, log line, or path is ever
/// rendered. The only live refresh (2 s, to the same bundled surface) happens
/// while the state can still change by itself (`bootstrap`, `starting`) or a
/// user-requested stop is in flight; every terminal state renders statically
/// until the user acts, so no state is silently retried.
#[must_use]
pub fn render_bootstrap(snapshot: &LifecycleSnapshot, api_origin: &str) -> String {
    let LifecycleSnapshot {
        state,
        failure,
        supervisor_pid,
        stop_pending,
        start_pending,
    } = snapshot;
    let origin = api_origin.trim_end_matches('/');
    // Live states: the view can still change by itself while a start or stop is
    // in flight, or while the state is bootstrap/starting. Every terminal
    // state renders statically and waits for the user — no automatic retry.
    let live = matches!(state, LifecycleState::Bootstrap | LifecycleState::Starting)
        || *stop_pending
        || *start_pending;
    let refresh = if live {
        format!(
            "<meta http-equiv=\"refresh\" content=\"2; url={BOOTSTRAP_SURFACE_URL}\">"
        )
    } else {
        String::new()
    };
    let service_line = match failure.as_ref().and_then(|record| record.service.clone()) {
        Some(service) => format!("Failing service: {service}"),
        None => "Failing service: not reported by the runtime".to_string(),
    };
    let diagnostics = match (state, failure, supervisor_pid, stop_pending) {
        (LifecycleState::Degraded, Some(record), _, _) => format!(
            "The runtime stopped after it was ready.{} [{}]. Only owned services were stopped; your data was retained. Choose Start for a single bounded recovery attempt, or Stop to leave the runtime stopped.",
            record
                .service
                .as_ref()
                .map(|service| format!(" Service '{service}' stopped reporting readiness."))
                .unwrap_or_default(),
            record.code,
        ),
        (LifecycleState::Failed, Some(record), _, _) => format!(
            "Startup failed [{}].{}{} No second service tree was started; your data was retained. Resolve the cause, then choose Start for one more attempt, or close the window.",
            record.code,
            record
                .service
                .as_ref()
                .map(|service| format!(" Failing service: {service}."))
                .unwrap_or_default(),
            record
                .detail
                .as_ref()
                .map(|detail| format!(" Occupied dependency: {detail}."))
                .unwrap_or_default(),
        ),
        (LifecycleState::Failed, None, _, _) => {
            "Startup failed. No second service tree was started; your data was retained."
                .to_string()
        }
        (LifecycleState::ShutdownFailed, Some(record), _, _) => format!(
            "Graceful stop did not complete [{}]. The runtime is waiting for an explicit stop retry; nothing outside the owned tree was touched and your data was retained. Choose Stop to retry the graceful shutdown, or close the window.",
            record.code,
        ),
        (LifecycleState::ShutdownFailed, None, _, _) => {
            "Graceful stop did not complete. The runtime is waiting for an explicit stop retry; nothing outside the owned tree was touched and your data was retained. Choose Stop to retry the graceful shutdown, or close the window."
                .to_string()
        }
        (LifecycleState::Starting, _, Some(pid), true) => format!(
            "Stop requested while starting (supervisor {pid}); cancelling startup and stopping only the owned services."
        ),
        (LifecycleState::Starting, _, Some(pid), false) => format!(
            "Starting owned services (supervisor {pid}); waiting for {origin}/health/ready. Choose Stop to cancel; only owned services are stopped and your data is kept."
        ),
        (LifecycleState::Starting, _, None, true) => {
            "Stop requested while starting; cancelling startup and stopping only the owned services."
                .to_string()
        }
        (LifecycleState::Starting, _, None, false) => {
            "Starting owned services; waiting for backend readiness. Choose Stop to cancel."
                .to_string()
        }
        (LifecycleState::Ready, _, Some(pid), true) => format!(
            "Stop requested (supervisor {pid}); stopping owned services in reverse order. Your data is retained."
        ),
        (LifecycleState::Ready, _, _, _) => {
            format!("Backend ready at {origin}. Choose Stop to stop the owned runtime, or close the window to stop and quit.")
        }
        (LifecycleState::Stopped, _, _, _) => {
            "The runtime is stopped. Locks and ports are released; your data was retained. Choose Start to run it again."
                .to_string()
        }
        (LifecycleState::Bootstrap, _, _, _) if !*start_pending => {
            "Local runtime bootstrap. No service is started yet. Choose Start to start the owned runtime for this workspace."
                .to_string()
        }
        (_, _, _, true) => {
            "Start requested; starting the owned services for this workspace. The runtime starts once and reports its real outcome."
                .to_string()
        }
        (LifecycleState::Bootstrap, _, _, _) => {
            "Local runtime bootstrap. No service is started yet. Choose Start to start the owned runtime for this workspace."
                .to_string()
        }
        (LifecycleState::Degraded, None, _, _) => {
            "The runtime stopped after it was ready. Your data was retained. Choose Start for a single bounded recovery attempt, or Stop to leave the runtime stopped."
                .to_string()
        }
    };
    let start_disabled = matches!(
        state,
        LifecycleState::Starting | LifecycleState::Ready | LifecycleState::ShutdownFailed
    ) || *start_pending;
    let stop_disabled = matches!(state, LifecycleState::Stopped | LifecycleState::Bootstrap)
        || (matches!(state, LifecycleState::Ready) && *stop_pending);
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
#service {{ margin-top: .5rem; color: #8a1c1c; }}
#diagnostics {{ white-space: pre-wrap; margin-top: 1rem; color: #444; }}
button {{ margin-right: .5rem; padding: .4rem 1rem; }}
button:disabled {{ opacity: .5; }}
</style>
</head>
<body>
<h1>Projecta</h1>
<p>State: <span id="state" data-testid="lifecycle-state">{}</span></p>
<form method="get" action="{BOOTSTRAP_SURFACE_URL}runtime" data-testid="lifecycle-runtime-form">
<button id="start" type="submit" name="intent" value="start" data-testid="lifecycle-start" {start_attribute}>Start</button>
<button id="stop" type="submit" name="intent" value="stop" data-testid="lifecycle-stop" {stop_attribute}>Stop</button>
</form>
<p id="service" data-testid="lifecycle-failing-service">{service_line}</p>
<pre id="diagnostics" data-testid="lifecycle-diagnostics">{diagnostics}</pre>
</body>
</html>"#,
        state.as_str(),
        start_attribute = if start_disabled { "disabled" } else { "" },
        stop_attribute = if stop_disabled { "disabled" } else { "" },
        service_line = service_line,
        diagnostics = diagnostics,
    )
}

/// Escape a value for a text node or a double-quoted HTML attribute.
///
/// The first-run surface is the one place a user-supplied string re-enters
/// HTML, so it is escaped with the full five-character set (`& < > " '`) even
/// though the value is already validated to be non-empty, ≤128 characters, and
/// free of C0 control characters.
#[must_use]
fn escape_html(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len());
    for character in value.chars() {
        match character {
            '&' => escaped.push_str("&amp;"),
            '<' => escaped.push_str("&lt;"),
            '>' => escaped.push_str("&gt;"),
            '"' => escaped.push_str("&quot;"),
            '\'' => escaped.push_str("&#39;"),
            other => escaped.push(other),
        }
    }
    escaped
}

/// Validate a first-run workspace display name against the exact rule the
/// audited Python `provision_first_run_workspace` applies, so an invalid name
/// is refused here and never reaches a child process that could write state.
///
/// The name must be non-empty after trimming, at most 128 characters, and free
/// of C0 control characters. The generated project ID must match the launcher
/// `PROJECT_ID_PATTERN` (`^[a-z0-9][a-z0-9-]{0,62}$`). Returns the trimmed
/// name on success, or the finite refusal code on failure.
#[must_use]
pub fn validate_workspace_name(raw: &str) -> Result<String, &'static str> {
    let trimmed = raw.trim();
    if trimmed.is_empty() || trimmed.chars().count() > 128 {
        return Err("WORKSPACE_NAME_INVALID");
    }
    if trimmed.chars().any(|character| (character as u32) < 0x20) {
        return Err("WORKSPACE_NAME_INVALID");
    }
    if !matches_project_id_pattern(trimmed) {
        return Err("WORKSPACE_NAME_INVALID");
    }
    Ok(trimmed.to_string())
}

/// Slug the display name exactly like `_slugify_first_run_project_id`, then
/// assert the launcher project-ID pattern (`^[a-z0-9][a-z0-9-]{0,62}$`).
/// The Python slugger truncates a long slug to 63 characters and prefixes a
/// leading digit, so a valid display name always yields a valid project ID;
/// the check stays as defense in depth.
fn matches_project_id_pattern(name: &str) -> bool {
    let mut slug: String = String::new();
    let mut pending_separator = false;
    for character in name.chars() {
        if character.is_ascii_lowercase() || character.is_ascii_digit() {
            if pending_separator && !slug.is_empty() {
                slug.push('-');
            }
            pending_separator = false;
            slug.push(character);
        } else {
            pending_separator = true;
        }
    }
    if slug.is_empty() {
        // `_slugify_first_run_project_id` falls back to the fixed default ID.
        return true;
    }
    if slug.starts_with(|character: char| character.is_ascii_digit()) {
        slug = format!("project-{slug}");
    }
    let trimmed: String = slug.chars().take(63).collect();
    if trimmed.is_empty() {
        return false;
    }
    let mut characters = trimmed.chars();
    let first = characters.next().unwrap_or_default();
    first.is_ascii_lowercase() || first.is_ascii_digit()
}

/// Render the first-run workspace form for the SAME main window: window chrome
/// plus a name field and Create/Cancel controls only. No API dependency and no
/// JavaScript exist in this state.
///
/// The form's `action` targets the WebView2 workaround URI
/// (`http://projecta-bootstrap.localhost/provision`) because the platform cannot
/// navigate directly to a non-standard scheme; wry reverts that URI back to
/// `projecta-bootstrap://localhost/provision` before the custom protocol handler
/// serves it, and the S15-03 navigation guard is extended to allow exactly that
/// locally generated workaround host. No new Tauri command, capability, or CSP
/// entry is introduced, and no script is served, so the trusted-origin and
/// navigation invariants are unchanged.
///
/// The placeholder offers the launcher's own default name; nothing is written
/// until the user submits, so a cancelled or invalid entry leaves no partial
/// customer state.
///
/// Content is sanitized: only a finite refusal code is echoed. No secret, key,
/// PID, or service output is ever rendered.
#[must_use]
pub fn render_first_run(default_name: &str, refusal_code: Option<&str>) -> String {
    let escaped_placeholder = escape_html(default_name);
    let readdressed = if let Some(code) = refusal_code {
        format!(
            "<p id=\"refusal\" data-testid=\"first-run-refusal\">That name is not accepted [{code}]. Enter a non-empty name of at most 128 characters.</p>"
        )
    } else {
        String::new()
    };
    format!(
        r#"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Projecta</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
#refusal {{ color: #8a1c1c; }}
form {{ margin-top: 1rem; }}
label {{ display: block; margin-bottom: .35rem; }}
input {{ padding: .4rem; width: 24rem; max-width: 100%; }}
button {{ margin-top: .75rem; margin-right: .5rem; padding: .4rem 1rem; }}
</style>
</head>
<body>
<h1>Projecta</h1>
<p>Create your local workspace. This computer only: nothing is uploaded, and a name you cannot identify is refused.</p>
{readdressed}
<form method="get" action="http://{BOOTSTRAP_WORKAROUND_HOST}/provision" data-testid="first-run-form">
<label for="workspace-name">Workspace name</label>
<input id="workspace-name" name="name" type="text" maxlength="128" placeholder="{escaped_placeholder}" data-testid="first-run-name">
<div>
<button type="submit" name="intent" value="create" data-testid="first-run-create">Create workspace</button>
<button type="submit" name="intent" value="cancel" data-testid="first-run-cancel">Cancel</button>
</div>
</form>
</body>
</html>"#
    )
}

/// App-owned lifecycle controller: spawn/stop exactly one supervisor child,
/// poll readiness, and track the window state for the same-window runtime
/// surface (bootstrap/first-run ⇄ lifecycle surface ⇄ SPA). The blocking
/// `cold_start` runs on a worker thread while window-close handling signals
/// cancellation from the event loop, and user Start/Stop from the surface or
/// the native Runtime menu drive the same bounded, single-attempt operations.
pub struct LifecycleController {
    paths: Option<LifecyclePaths>,
    api_port: u16,
    state: Mutex<LifecycleState>,
    failure: Mutex<Option<FailureRecord>>,
    supervisor: Mutex<Option<OwnedSupervisor>>,
    cancel: AtomicBool,
    /// Whether a user/auto start is in flight on a worker thread. The surface
    /// must keep refreshing while a start can still change the state by
    /// itself, and a second user Start must not race an in-flight worker.
    start_pending: AtomicBool,
    /// Whether a user-requested stop is in flight on a worker thread. Only the
    /// surface renders it; the stop itself never blocks the window.
    stop_pending: AtomicBool,
    startup_handle: Mutex<Option<JoinHandle<bool>>>,
    /// Whether the data root had no workspace when this app launched. Read once
    /// in `new` (before provisioning), then cleared only by a successful
    /// `provision_first_run`, so a window that has just created its workspace
    /// does not re-decide it is still first-run and re-show the form.
    first_run: AtomicBool,
}

impl LifecycleController {
    #[must_use]
    pub fn new(paths: Option<LifecyclePaths>, api_port: u16) -> Self {
        // First-run is decided once, before anything is provisioned.
        let first_run = matches!(&paths, Some(paths) if !paths.has_workspace());
        Self {
            paths,
            api_port,
            state: Mutex::new(LifecycleState::Bootstrap),
            failure: Mutex::new(None),
            supervisor: Mutex::new(None),
            cancel: AtomicBool::new(false),
            start_pending: AtomicBool::new(false),
            stop_pending: AtomicBool::new(false),
            startup_handle: Mutex::new(None),
            first_run: AtomicBool::new(first_run),
        }
    }

    /// Whether the launched data root has no workspace yet, so the window must
    /// show the first-run form instead of starting the owned tree.
    #[must_use]
    pub fn is_first_run(&self) -> bool {
        self.first_run.load(Ordering::SeqCst)
    }

    #[must_use]
    pub fn state(&self) -> LifecycleState {
        *self.state.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// The sanitized failure record currently presented (finite code, optional
    /// failing service, optional occupied-port observation), if any.
    #[must_use]
    pub fn failure(&self) -> Option<FailureRecord> {
        self.failure
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .clone()
    }

    /// Finite failure code currently presented, if any.
    #[must_use]
    #[allow(dead_code)]
    pub fn failure_code(&self) -> Option<String> {
        self.failure().map(|record| record.code)
    }

    /// The failing service the supervisor reported, if any.
    #[must_use]
    pub fn failure_service(&self) -> Option<String> {
        self.failure().and_then(|record| record.service)
    }

    /// Whether a user-requested stop is in flight on a worker thread.
    #[must_use]
    pub fn is_stop_pending(&self) -> bool {
        self.stop_pending.load(Ordering::SeqCst)
    }

    /// Whether a start is in flight on a worker thread (set before the worker
    /// runs, cleared when it finishes). The surface keeps refreshing while it
    /// is set, and a second user Start is refused so it cannot race the worker.
    #[must_use]
    pub fn is_start_pending(&self) -> bool {
        self.start_pending.load(Ordering::SeqCst)
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

    /// Whether the owned supervisor child exists and is still running. The
    /// manager owns service supervision; the desktop only observes this handle,
    /// never another process.
    #[must_use]
    pub fn owned_supervisor_alive(&self) -> bool {
        self.supervisor
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .as_mut()
            .is_some_and(OwnedSupervisor::is_running)
    }

    /// Whether a user-initiated Start can legitimately run now. Starting twice
    /// or starting while ready is refused rather than turned into a silent
    /// success screen, and a start is refused while an owned supervisor handle
    /// still exists (for example the manager waiting in `shutdown-failed` for
    /// its explicit stop retry), so the surface never tries to start a second
    /// tree over a live manager.
    #[must_use]
    pub fn can_start(&self) -> bool {
        !matches!(
            self.state(),
            LifecycleState::Starting | LifecycleState::Ready
        ) && !self.has_supervisor()
            && !self.is_first_run()
            && !self.is_start_pending()
    }

    fn set_state(&self, state: LifecycleState, failure: Option<FailureRecord>) {
        *self.state.lock().unwrap_or_else(|e| e.into_inner()) = state;
        *self.failure.lock().unwrap_or_else(|e| e.into_inner()) = failure;
    }

    /// Record a terminal failure state from the supervisor's finite code and
    /// optional failing service. The record is sanitized on construction; a
    /// `PORT_IN_USE` code additionally observes which fixed port is occupied
    /// exactly once, at record time.
    fn set_failure(&self, state: LifecycleState, code: String, service: Option<String>) {
        let record = FailureRecord::new(code, service);
        self.set_state(state, Some(record));
    }

    /// Snapshot for the lifecycle surface renderer.
    pub fn snapshot(&self) -> LifecycleSnapshot {
        LifecycleSnapshot {
            state: self.state(),
            failure: self.failure(),
            supervisor_pid: self.supervisor_pid(),
            stop_pending: self.is_stop_pending(),
            start_pending: self.is_start_pending(),
        }
    }

    /// Stash the worker-thread handle running `cold_start` (setup path).
    pub fn set_startup_handle(&self, handle: JoinHandle<bool>) {
        *self.startup_handle.lock().unwrap_or_else(|e| e.into_inner()) = Some(handle);
    }

    /// Run `cold_start` on a worker thread and keep its handle so the close path
    /// can join it exactly once. Used by the auto-start (existing workspace)
    /// path, the first-run provision path, and user Start from the surface or
    /// the native Runtime menu. A previous startup worker has already returned
    /// by the time a new start is allowed (its outcome is what produced the
    /// non-starting state), so the stashed handle is joined and dropped rather
    /// than asserted away: a second tree is still prevented by `cold_start`
    /// itself and by the `can_start` guard.
    pub fn spawn_cold_start(self: &std::sync::Arc<Self>) {
        // A previous startup worker has already returned (a new start is only
        // reachable from a non-starting state with no in-flight worker), so its
        // stashed handle is joined and dropped rather than asserted away: a
        // second tree is still prevented by `cold_start` and the `can_start`
        // guard. The flag marks the in-flight window so the surface keeps
        // refreshing (the worker sets `starting` moments later) and a second
        // user Start cannot race this worker.
        if let Some(previous) = self.take_startup_handle() {
            let _ = previous.join();
        }
        self.start_pending.store(true, Ordering::SeqCst);
        let worker = Arc::clone(self);
        let startup_thread = std::thread::spawn(move || {
            let outcome = worker.cold_start();
            worker.start_pending.store(false, Ordering::SeqCst);
            outcome
        });
        self.set_startup_handle(startup_thread);
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
            self.set_failure(LifecycleState::Failed, "ALREADY_STARTED".to_string(), None);
            return false;
        }
        let Some(paths) = self.paths.clone() else {
            self.set_failure(
                LifecycleState::Failed,
                "RUNTIME_PACKAGE_MISSING".to_string(),
                None,
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
                self.set_failure(
                    LifecycleState::Failed,
                    "SUPERVISOR_SPAWN_FAILED".to_string(),
                    None,
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
            let (code, service) = self.reap_supervisor_failure();
            self.set_failure(LifecycleState::Failed, code, service);
            return false;
        }
        // Wait for real readiness, checking cancellation every poll. The
        // manager owns service supervision, so its exit is the failure signal:
        // a start attempt adopts the manager's own finite record instead of
        // polling past it until the deadline. No automatic recovery or
        // restart on failure.
        let started = Instant::now();
        while started.elapsed() < STARTUP_DEADLINE {
            if self.cancel_requested() {
                self.cancel_start();
                return false;
            }
            let alive = self
                .supervisor
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .as_mut()
                .is_some_and(OwnedSupervisor::is_running);
            if alive
                && poll_api_ready(self.api_port, Duration::from_secs(2)) == Readiness::Ready
            {
                self.set_state(LifecycleState::Ready, None);
                return true;
            }
            if !alive {
                // The manager exited during startup (for example it refused a
                // port collision and failed closed): adopt its own record.
                let (code, service) = self.reap_supervisor_failure();
                self.set_failure(LifecycleState::Failed, code, service);
                return false;
            }
            std::thread::sleep(Duration::from_millis(500));
        }
        if self.cancel_requested() {
            self.cancel_start();
            return false;
        }
        // Startup deadline passed with the manager still running: stop only the
        // owned child, release locks/ports, retain data.
        let still_running = self
            .supervisor
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .as_mut()
            .is_some_and(OwnedSupervisor::is_running);
        if still_running {
            self.stop_owned(STOP_TIMEOUT);
            self.set_failure(
                LifecycleState::Failed,
                "SERVICE_READINESS_TIMEOUT".to_string(),
                None,
            );
        } else {
            let (code, service) = self.reap_supervisor_failure();
            self.set_failure(LifecycleState::Failed, code, service);
        }
        false
    }

    /// Reap the owned supervisor child and extract the manager's finite failure
    /// record. The supervisor's own stderr tail names the code for THIS child,
    /// and the owned status document contributes the failing service name when
    /// it reports the same code; a status code without a matching stderr code is
    /// only used when the child printed nothing (it was reaped after an
    /// abnormal exit). No other source is consulted, so no stale or foreign
    /// state can be misattributed to this run.
    fn reap_supervisor_failure(&self) -> (String, Option<String>) {
        let stderr_code = self
            .supervisor
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .take()
            .map(|mut supervisor| supervisor.reap_failure_code())
            .filter(|code| code != "SUPERVISOR_EXITED");
        let status_failure = self
            .paths
            .as_ref()
            .and_then(LifecyclePaths::read_runtime_status)
            .and_then(|status| status.failure);
        match (stderr_code, status_failure) {
            (Some(code), Some(record)) if record.code == code => (code, record.service),
            (Some(code), _) => (code, None),
            (None, Some(record)) => (record.code, record.service),
            (None, None) => ("SUPERVISOR_EXITED".to_string(), None),
        }
    }

    /// Create the first-run workspace from the SAME main window, then start the
    /// owned tree.
    ///
    /// Single attempt, bounded, no retry: an invalid name is refused in Rust
    /// (mirroring the audited Python rule) so no child process is even spawned,
    /// and every CLI failure maps to the launcher's own finite code. On success
    /// the window straight into the ordinary cold start, so provisioning is one
    /// continuous first-run journey rather than a second user action.
    ///
    /// Non-destructive by construction: the launcher's `provision` subcommand
    /// refuses to overwrite an existing `local-runtime.json`, so an existing
    /// workspace is never reseeded. This method also refuses to run at all once
    /// this process has created a workspace.
    pub fn provision_first_run(&self, raw_name: &str) -> Result<(), String> {
        if self.has_supervisor() {
            return Err("ALREADY_STARTED".to_string());
        }
        let Some(paths) = self.paths.clone() else {
            // No bundled package at all: fail closed with the finite code rather
            // than showing a first-run form that could never provision.
            self.set_failure(
                LifecycleState::Failed,
                "RUNTIME_PACKAGE_MISSING".to_string(),
                None,
            );
            return Err("RUNTIME_PACKAGE_MISSING".to_string());
        };
        if !self.first_run.load(Ordering::SeqCst) {
            // An existing workspace is present (or was just created): nothing
            // to provision. Never reseed, never overwrite.
            return Err("WORKSPACE_ALREADY_PROVISIONED".to_string());
        }
        let trimmed = match validate_workspace_name(raw_name) {
            Ok(trimmed) => trimmed,
            // A refused name changes nothing: no state transition, no child
            // process, no file written.
            Err(code) => return Err(code.to_string()),
        };
        self.set_state(LifecycleState::Starting, None);
        if let Err(code) = paths.provision_workspace(&trimmed) {
            self.set_failure(LifecycleState::Failed, code.clone(), None);
            return Err(code);
        }
        // Provisioning is complete; this process owns the workspace now.
        self.first_run.store(false, Ordering::SeqCst);
        Ok(())
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
            self.set_failure(
                LifecycleState::ShutdownFailed,
                "GRACEFUL_STOP_TIMEOUT".to_string(),
                None,
            );
            return false;
        }
        if self.state() != LifecycleState::Stopped {
            let failure = self.failure();
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

    /// User-initiated Start from the lifecycle surface or the native Runtime
    /// menu: a single bounded attempt through the existing `start` operation.
    ///
    /// Refused without any state change when a start is already running or the
    /// tree is already ready (no silent second attempt and no empty success
    /// screen), and when the data root is still awaiting first-run provisioning
    /// (the first-run form owns that path). Returns whether a start was begun.
    pub fn user_start(self: &std::sync::Arc<Self>) -> bool {
        if !self.can_start() {
            return false;
        }
        // A previous close/cancel may have set the cancel flag; a new explicit
        // user Start clears it so the new attempt is not cancelled instantly.
        self.cancel.store(false, Ordering::SeqCst);
        self.spawn_cold_start();
        true
    }

    /// Mark a user-requested stop as in flight synchronously, before any
    /// navigation happens. The window bindsings call this first and navigate
    /// afterwards, so every render the user can see after a Stop action is a
    /// live view that keeps refreshing until the manager's own terminal
    /// outcome arrives — the surface can never freeze on a stale pre-action
    /// render, and no state is invented here.
    pub fn begin_user_stop(&self) {
        self.stop_pending.store(true, Ordering::SeqCst);
    }

    /// User-initiated Stop from the lifecycle surface or the native Runtime
    /// menu. Runs the manager's own reverse-order shutdown on the calling
    /// thread (callers must not block the window): during `starting` it is the
    /// bounded mid-start cancel; afterwards it is the graceful `stop` request
    /// with the manager's own timeouts.
    ///
    /// The manager owns the `shutdown-failed` policy: while it is alive and
    /// reports `shutdown-failed` it is waiting for this explicit stop retry, so
    /// the desktop reports that state instead of terminating the manager. If
    /// the bound expires while a healthy manager is still shutting down, the
    /// owned child is left alone and the post-ready watcher adopts its eventual
    /// exit — the surface never invents a success or a failure the manager did
    /// not report.
    pub fn complete_user_stop(&self) -> StopOutcome {
        self.begin_user_stop();
        let outcome = if self.state() == LifecycleState::Starting {
            self.request_cancel();
            if let Some(startup) = self.take_startup_handle() {
                let _ = startup.join();
            }
            self.cancel_start();
            StopOutcome::Stopped
        } else {
            self.stop_owned_for_surface()
        };
        self.stop_pending.store(false, Ordering::SeqCst);
        outcome
    }

    /// Graceful stop for the surface Stop control: request the manager's own
    /// reverse-order shutdown and wait for its own outcome. Unlike the close
    /// path, the owned manager is never terminated here.
    fn stop_owned_for_surface(&self) -> StopOutcome {
        let Some(paths) = self.paths.clone() else {
            return StopOutcome::Stopped;
        };
        {
            let mut guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
            let Some(supervisor) = guard.as_mut() else {
                return StopOutcome::Stopped;
            };
            if !supervisor.is_running() {
                guard.take();
                return StopOutcome::Stopped;
            }
        }
        paths.request_stop();
        let deadline = Instant::now() + STOP_REQUEST_BOUND;
        loop {
            {
                let mut guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
                let Some(supervisor) = guard.as_mut() else {
                    return StopOutcome::Stopped;
                };
                if !supervisor.is_running() {
                    guard.take();
                    return StopOutcome::Stopped;
                }
            }
            // The manager publishes `shutdown-failed` while it waits for the
            // explicit stop retry; honour that instead of terminating it.
            if let Some(status) = paths.read_runtime_status() {
                if status.state.as_deref() == Some("shutdown-failed") {
                    let code = status
                        .failure
                        .map(|record| record.code)
                        .unwrap_or_else(|| "GRACEFUL_STOP_TIMEOUT".to_string());
                    self.set_failure(LifecycleState::ShutdownFailed, code, None);
                    return StopOutcome::ShutdownFailed;
                }
            }
            if Instant::now() >= deadline {
                // Still inside the manager's own bounded reverse-order stop:
                // leave the owned child running and keep the current state so
                // the watcher adopts the manager's real terminal outcome.
                return StopOutcome::Stopped;
            }
            std::thread::sleep(STOP_STATUS_POLL);
        }
    }

    /// Adopt the owned manager's exit after the window had shown the SPA: reap
    /// the child, read the manager's own terminal status, and present the
    /// contract's post-ready outcome. A supervisor-reported failure becomes
    /// `degraded` with its finite code and failing service; a clean stop becomes
    /// `stopped`; anything else is `degraded` with the finite fallback code. No
    /// automatic restart happens here — recovery stays user-initiated.
    pub fn adopt_supervisor_exit_after_ready(&self) {
        if self.state() != LifecycleState::Ready {
            return;
        }
        let (code, service) = self.reap_supervisor_failure();
        let status_state = self
            .paths
            .as_ref()
            .and_then(LifecyclePaths::read_runtime_status)
            .and_then(|status| status.state);
        if code == "SUPERVISOR_EXITED" && status_state.as_deref() == Some("stopped") {
            self.set_state(LifecycleState::Stopped, None);
            return;
        }
        self.set_failure(LifecycleState::Degraded, code, service);
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
                self.set_failure(
                    self.state(),
                    "GRACEFUL_STOP_TIMEOUT".to_string(),
                    self.failure_service(),
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
        BOOTSTRAP_SCHEME, BOOTSTRAP_SURFACE_URL, DEFAULT_API_PORT, FailureRecord, LOOPBACK_HOST,
        LifecycleController, LifecyclePaths, LifecycleSnapshot, LifecycleState, Readiness,
        StopOutcome, api_origin, bootstrap_url, extract_failure_code, is_allowed_navigation,
        is_finite_code, is_service_name, poll_api_ready, render_bootstrap, render_first_run,
        validate_workspace_name,
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
            // A lookalike workaround host must NOT be accepted: only the exact
            // platform-generated prefix is.
            "http://projecta-bootstrap.evil.test/",
            "http://bootstrap.localhost/",
            "http://projecta-bootstrap.localhost.example.test/",
            "http://projecta-bootstrap.localhost:8080/provision?intent=create&name=X",
            "http://user@projecta-bootstrap.localhost/provision",
            "projecta-bootstrap://localhost:8080/",
        ] {
            let url: url::Url = raw.parse().expect("valid URL");
            assert!(
                !is_allowed_navigation(&url, &origin),
                "must refuse navigation to {raw}"
            );
        }
        // WebView2's own rewrite of the bundled bootstrap surface is local and
        // allowed, because it is how the platform navigates to a custom scheme.
        let workaround: url::Url = "http://projecta-bootstrap.localhost/provision?intent=create&name=X"
            .parse()
            .expect("valid workaround URL");
        assert!(is_allowed_navigation(&workaround, &origin));
        let explicit_default_port: url::Url =
            "http://projecta-bootstrap.localhost:80/provision?intent=create&name=X"
                .parse()
                .expect("valid default-port workaround URL");
        assert!(is_allowed_navigation(&explicit_default_port, &origin));
    }

    #[test]
    fn lifecycle_states_cover_contract_transitions() {
        assert_eq!(LifecycleState::Bootstrap.as_str(), "bootstrap");
        assert_eq!(LifecycleState::Starting.as_str(), "starting");
        assert_eq!(LifecycleState::Ready.as_str(), "ready");
        assert_eq!(LifecycleState::Degraded.as_str(), "degraded");
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
    fn lifecycle_surface_exposes_real_controls_and_states() {
        let origin = format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/");
        let starting = render_bootstrap(
            &LifecycleSnapshot {
                state: LifecycleState::Starting,
                failure: None,
                supervisor_pid: Some(1234),
                stop_pending: false,
                start_pending: false,
            },
            &origin,
        );
        // One form in the same window submits the runtime intents; no script,
        // no Tauri command, no capability is introduced.
        assert!(starting.contains("data-testid=\"lifecycle-state\""));
        assert!(starting.contains("data-testid=\"lifecycle-runtime-form\""));
        assert!(starting.contains("data-testid=\"lifecycle-start\""));
        assert!(starting.contains("data-testid=\"lifecycle-stop\""));
        assert!(starting.contains("data-testid=\"lifecycle-diagnostics\""));
        assert!(!starting.contains("<script"));
        // Starting cannot start again (no second tree) but can be cancelled.
        assert!(starting.contains("data-testid=\"lifecycle-start\" disabled"));
        assert!(!starting.contains("data-testid=\"lifecycle-stop\" disabled"));
        // Only a live state refreshes the view (never a service retry), and the
        // refresh target is the exact bundled workaround origin the guard
        // already allows.
        let refresh = format!("http-equiv=\"refresh\" content=\"2; url={BOOTSTRAP_SURFACE_URL}");
        assert!(starting.contains(&refresh));

        let stopped = render_bootstrap(
            &LifecycleSnapshot {
                state: LifecycleState::Stopped,
                failure: None,
                supervisor_pid: None,
                stop_pending: false,
                start_pending: false,
            },
            &origin,
        );
        // Stopped is the recovery entry point: Start enabled, Stop meaningless.
        assert!(!stopped.contains("data-testid=\"lifecycle-start\" disabled"));
        assert!(stopped.contains("data-testid=\"lifecycle-stop\" disabled"));
        // A terminal state never auto-refreshes: nothing retries by itself.
        assert!(!stopped.contains("http-equiv=\"refresh\""));
    }

    #[test]
    fn degraded_surface_names_the_failing_dependency_and_recovery() {
        let html = render_bootstrap(
            &LifecycleSnapshot {
                state: LifecycleState::Degraded,
                failure: Some(FailureRecord::new(
                    "SERVICE_BECAME_UNREADY".to_string(),
                    Some("fuseki".to_string()),
                )),
                supervisor_pid: None,
                stop_pending: false,
                start_pending: false,
            },
            &format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/"),
        );
        // The failing dependency and its finite code are surfaced, never an
        // empty success screen, and recovery is offered but never automatic.
        assert!(html.contains("degraded"));
        assert!(html.contains("SERVICE_BECAME_UNREADY"));
        assert!(html.contains("fuseki"));
        assert!(!html.contains("http-equiv=\"refresh\""));
        assert!(!html.contains("data-testid=\"lifecycle-start\" disabled"));
    }

    #[test]
    fn shutdown_failed_surface_offers_the_explicit_stop_retry_only() {
        let html = render_bootstrap(
            &LifecycleSnapshot {
                state: LifecycleState::ShutdownFailed,
                failure: Some(FailureRecord::new(
                    "GRACEFUL_STOP_TIMEOUT".to_string(),
                    None,
                )),
                supervisor_pid: None,
                stop_pending: false,
                start_pending: false,
            },
            &format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/"),
        );
        // The finite shutdown code stays visible, the retry stays available,
        // and nothing stops itself.
        assert!(html.contains("GRACEFUL_STOP_TIMEOUT"));
        assert!(!html.contains("http-equiv=\"refresh\""));
        assert!(!html.contains("data-testid=\"lifecycle-stop\" disabled"));
        // The manager owns the stop retry; a start cannot apply here.
        assert!(html.contains("data-testid=\"lifecycle-start\" disabled"));
    }

    #[test]
    fn port_in_use_failure_renders_the_occupied_dependency() {
        // The surface must present the finite code and name the occupied
        // dependency for a PORT_IN_USE failure, with user-initiated recovery
        // and no automatic retry. The record is built directly here so the
        // invariant is deterministic on any host; which fixed port is actually
        // occupied is owned by the manager's own refusal and is exercised by
        // the retained disposable native collision smoke, never by binding
        // host ports in a test.
        let html = render_bootstrap(
            &LifecycleSnapshot {
                state: LifecycleState::Failed,
                failure: Some(FailureRecord {
                    code: "PORT_IN_USE".to_string(),
                    service: None,
                    detail: Some("api on port 18732".to_string()),
                }),
                supervisor_pid: None,
                stop_pending: false,
                start_pending: false,
            },
            &format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/"),
        );
        // Consumer semantics: finite code, failing dependency + port, recovery.
        assert!(html.contains("PORT_IN_USE"));
        assert!(html.contains("api"));
        assert!(html.contains("18732"));
        // Still a finite failure screen: no auto-retry, recovery is the user's.
        assert!(!html.contains("http-equiv=\"refresh\""));
        assert!(!html.contains("data-testid=\"lifecycle-start\" disabled"));
    }

    #[test]
    fn finite_code_and_service_filters_refuse_arbitrary_text() {
        assert!(is_finite_code("SERVICE_BECAME_UNREADY"));
        assert!(is_finite_code("PORT_IN_USE"));
        for rejected in [
            "",
            "lower_case",
            "has space",
            "has-dash",
            "unicode-\u{00e9}",
            &"x".repeat(65),
        ] {
            assert!(!is_finite_code(rejected), "must refuse {rejected:?}");
        }
        assert!(is_service_name("postgres"));
        assert!(is_service_name("fuseki"));
        assert!(is_service_name("semanticCore"));
        assert!(is_service_name("api"));
        assert!(!is_service_name("other"));
        assert!(!is_service_name("api; DROP TABLE"));
    }

    #[test]
    fn runtime_status_reading_is_sanitized() {
        let data_root = disposable_root("s15-05-runtime-status");
        std::fs::create_dir_all(data_root.join("state")).expect("state dir");
        let paths = nonexistent_paths(&data_root);
        // A well-formed supervisor document yields its sanitized view.
        std::fs::write(
            data_root.join("state/runtime.json"),
            serde_json::json!({
                "formatVersion": 1,
                "state": "failed",
                "failureCode": "SERVICE_BECAME_UNREADY",
                "failedService": "fuseki",
                "url": null,
            })
            .to_string(),
        )
        .expect("write status");
        let status = paths.read_runtime_status().expect("readable status");
        assert_eq!(status.state.as_deref(), Some("failed"));
        let failure = status.failure.expect("failure record");
        assert_eq!(failure.code, "SERVICE_BECAME_UNREADY");
        assert_eq!(failure.service.as_deref(), Some("fuseki"));
        // An unexpected code, service, or state is dropped, not rendered.
        std::fs::write(
            data_root.join("state/runtime.json"),
            serde_json::json!({
                "state": "surprising",
                "failureCode": "<script>alert(1)</script>",
                "failedService": "not-a-service",
            })
            .to_string(),
        )
        .expect("write hostile status");
        let hostile = paths.read_runtime_status().expect("readable status");
        assert_eq!(hostile.state, None);
        assert!(hostile.failure.is_none());
        // Unreadable or non-object documents degrade to None.
        std::fs::write(data_root.join("state/runtime.json"), "[]").expect("write array status");
        assert!(paths.read_runtime_status().is_none());
        let _ = std::fs::remove_dir_all(&data_root);
    }

    #[test]
    fn user_start_is_bounded_and_never_a_second_attempt() {
        let controller = std::sync::Arc::new(LifecycleController::new(None, DEFAULT_API_PORT));
        // No package and no workspace: a start is refused before any child
        // exists, and the failure stays finite rather than a success screen.
        assert!(controller.can_start());
        assert!(controller.user_start());
        // Wait for the single bounded attempt to report its finite failure.
        if let Some(handle) = controller.take_startup_handle() {
            let _ = handle.join();
        }
        assert_eq!(controller.state(), LifecycleState::Failed);
        assert_eq!(
            controller.failure_code().as_deref(),
            Some("RUNTIME_PACKAGE_MISSING")
        );
        // While starting or ready, a second user Start is refused outright.
        controller.set_state(LifecycleState::Starting, None);
        assert!(!controller.can_start());
        assert!(!controller.user_start());
        controller.set_state(LifecycleState::Ready, None);
        assert!(!controller.can_start());
        assert!(!controller.user_start());
        // First-run never starts from the surface: the first-run form owns it.
        let first_run = LifecycleController::new(None, DEFAULT_API_PORT);
        first_run.first_run.store(true, std::sync::atomic::Ordering::SeqCst);
        assert!(!first_run.can_start());
    }

    #[test]
    fn user_stop_from_starting_cancels_and_leaves_the_cycle_restartable() {
        // Ready→Stop→Start boundary at controller level: a stop during a start
        // cancels the in-flight worker (single attempt, no retry) and lands in
        // `stopped`, after which exactly one further user Start is allowed.
        let controller = std::sync::Arc::new(LifecycleController::new(None, DEFAULT_API_PORT));
        controller.set_state(LifecycleState::Starting, None);
        assert!(!controller.can_start(), "a starting tree cannot start again");
        let outcome = controller.complete_user_stop();
        assert_eq!(outcome, StopOutcome::Stopped);
        assert_eq!(controller.state(), LifecycleState::Stopped);
        assert!(controller.cancel_requested());
        assert!(!controller.is_stop_pending());
        // A stop with no owned child is a clean stopped state, not a failure.
        assert!(controller.failure().is_none());
        // The cycle restarts exactly once per user action.
        assert!(controller.can_start());
        assert!(controller.user_start());
        if let Some(handle) = controller.take_startup_handle() {
            let _ = handle.join();
        }
        assert_eq!(controller.state(), LifecycleState::Failed);
        assert!(!controller.has_supervisor());
    }

    #[test]
    fn start_pending_blocks_a_second_start_and_keeps_the_view_live() {
        // Regression for the stale-surface race: while a start is in flight the
        // snapshot must keep refreshing (the worker sets `starting` moments
        // later), and a second user Start must be refused rather than racing
        // the in-flight worker.
        let controller = std::sync::Arc::new(LifecycleController::new(None, DEFAULT_API_PORT));
        assert!(controller.user_start());
        assert!(controller.is_start_pending());
        assert!(!controller.can_start(), "a second Start must not race the worker");
        assert!(!controller.user_start());
        // The in-flight start renders a live view even though the worker has
        // not yet flipped the state, so the real outcome is always shown.
        let origin = format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/");
        let pending = render_bootstrap(&controller.snapshot(), &origin);
        let refresh = format!("http-equiv=\"refresh\" content=\"2; url={BOOTSTRAP_SURFACE_URL}");
        assert!(pending.contains(&refresh));
        assert!(pending.contains("data-testid=\"lifecycle-start\" disabled"));
        if let Some(handle) = controller.take_startup_handle() {
            let _ = handle.join();
        }
        assert!(!controller.is_start_pending());
        // The worker finished with its finite failure; a later user Start is
        // allowed again exactly once per action.
        assert_eq!(controller.state(), LifecycleState::Failed);
        assert!(controller.can_start());
    }

    #[test]
    fn repeated_user_starts_do_not_panic_or_stack_workers() {
        // Regression: a user Start after a finished start episode must reuse the
        // stashed worker handle (join and drop) instead of panicking, and must
        // never leave two startup workers alive.
        let controller = std::sync::Arc::new(LifecycleController::new(None, DEFAULT_API_PORT));
        assert!(controller.user_start());
        if let Some(handle) = controller.take_startup_handle() {
            let _ = handle.join();
        }
        assert!(controller.user_start());
        if let Some(handle) = controller.take_startup_handle() {
            let _ = handle.join();
        }
        // The stashed handle is consumed again: exactly one worker exists.
        assert!(controller.take_startup_handle().is_none());
        assert_eq!(controller.state(), LifecycleState::Failed);
        assert!(!controller.has_supervisor());
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

    #[test]
    fn workspace_name_validation_matches_launcher_rule() {
        // Mirrors `provision_first_run_workspace`: non-empty after trim, at
        // most 128 characters, no C0 control characters, and a slug satisfying
        // the launcher project-ID pattern.
        assert_eq!(validate_workspace_name("  Team Notes  ").ok().as_deref(), Some("Team Notes"));
        assert_eq!(validate_workspace_name("My Projecta Workspace").ok().as_deref(), Some("My Projecta Workspace"));
        // A 128-character name is at the limit and is accepted: the slugger
        // truncates the generated project ID to 63 characters, exactly like
        // `_slugify_first_run_project_id`.
        let edge = "a".repeat(128);
        assert_eq!(validate_workspace_name(&edge).ok().as_deref(), Some(edge.as_str()));
        for rejected in ["", "   ", "a".repeat(129).as_str(), "bad\nname", "tab\tname"] {
            assert!(
                validate_workspace_name(rejected).is_err(),
                "must refuse invalid workspace name {rejected:?}"
            );
        }
        // Unicode parity with the launcher: a non-breaking space is whitespace
        // to both `str.strip` and `str::trim`, and a name whose every character
        // is non-ASCII still slugs to a valid project ID.
        assert!(validate_workspace_name("\u{00a0}").is_err());
        assert!(validate_workspace_name("日本語のワークスペース").is_ok());
        assert!(validate_workspace_name("Ünïcödé Näme").is_ok());
    }

    #[test]
    fn first_run_form_exposes_the_real_user_path() {
        let html = render_first_run("My Projecta Workspace", None);
        // One form, one main window: the Create control submits the name.
        assert!(html.contains("data-testid=\"first-run-form\""));
        assert!(html.contains("data-testid=\"first-run-create\""));
        assert!(html.contains("data-testid=\"first-run-cancel\""));
        // The action targets the SAME packaged surface through WebView2's
        // workaround host, so no new command, capability, or CSP entry is
        // required.
        assert!(html.contains("action=\"http://projecta-bootstrap.localhost/provision\""));
        // No script surface is introduced (CSP `script-src` is unchanged).
        assert!(!html.contains("<script"));
        // No secret, key, service output, or PID is rendered.
        assert!(!html.contains("dpapi"));
        assert!(!html.contains("launcher.dpapi"));
        assert!(!html.contains("postgres"));
        assert!(!html.to_lowercase().contains("secret"));
        assert!(!html.contains("managerPid"));
    }

    #[test]
    fn first_run_form_escapes_user_supplied_placeholder() {
        let escaped = render_first_run("a\"b<c>&d'e", None);
        // The raw metacharacters never reach an attribute or text node.
        assert!(escaped.contains("a&quot;b&lt;c&gt;&amp;d&#39;e"));
        assert!(!escaped.contains("a\"b<c>"));
    }

    #[test]
    fn first_run_refusal_renders_sanitized_finite_code() {
        let html = render_first_run("My Projecta Workspace", Some("WORKSPACE_NAME_INVALID"));
        assert!(html.contains("data-testid=\"first-run-refusal\""));
        assert!(html.contains("WORKSPACE_NAME_INVALID"));
        // The refusal is a finite code, never a raw launcher stderr line.
        assert!(!html.contains("Projecta Local:"));
    }

    #[test]
    fn first_run_detection_reads_existing_workspace_only() {
        let data_root = disposable_root("s15-04-first-run-detect");
        std::fs::create_dir_all(data_root.join("config")).expect("config dir");
        let paths = || LifecyclePaths {
            python_exe: std::path::PathBuf::from("C:/nonexistent/python.exe"),
            launcher_script: std::path::PathBuf::from("C:/nonexistent/projecta_local.py"),
            package_root: std::path::PathBuf::from("C:/nonexistent"),
            data_root: data_root.clone(),
        };
        // No `config/local-runtime.json` yet: this is a first-run data root.
        assert!(!paths().has_workspace());
        assert!(LifecycleController::new(Some(paths()), DEFAULT_API_PORT).is_first_run());
        // Once the registry exists, the same data root is an existing workspace.
        std::fs::write(data_root.join("config/local-runtime.json"), "{\"formatVersion\":1}")
            .expect("write registry");
        assert!(!LifecycleController::new(Some(paths()), DEFAULT_API_PORT).is_first_run());
        // No package at all cannot be a first run: fail closed to the ordinary
        // RUNTIME_PACKAGE_MISSING lifecycle path rather than showing a form that
        // could never provision.
        assert!(!LifecycleController::new(None, DEFAULT_API_PORT).is_first_run());
        let _ = std::fs::remove_dir_all(&data_root);
    }

    #[test]
    fn provisioning_refuses_without_a_package_and_leaves_no_state() {
        let controller = LifecycleController::new(None, DEFAULT_API_PORT);
        assert!(!controller.is_first_run());
        assert!(controller.provision_first_run("Any Name").is_err());
        assert_eq!(
            controller.failure_code().as_deref(),
            Some("RUNTIME_PACKAGE_MISSING")
        );
        // Still no supervisor child was spawned: nothing to stop.
        assert!(!controller.has_supervisor());
        assert!(controller.shutdown());
    }

    #[test]
    fn provisioning_refuses_an_invalid_name_before_spawning_anything() {
        let data_root = disposable_root("s15-04-invalid-name");
        let controller = LifecycleController::new(Some(nonexistent_paths(&data_root)), DEFAULT_API_PORT);
        assert!(controller.is_first_run());
        // An invalid name is refused in-process, so the (nonexistent) launcher
        // is never invoked and no workspace config can be written.
        let refused = controller.provision_first_run("bad\nname");
        assert_eq!(refused.err().as_deref(), Some("WORKSPACE_NAME_INVALID"));
        assert!(!data_root.join("config/local-runtime.json").is_file());
        assert!(!controller.has_supervisor());
        let _ = std::fs::remove_dir_all(&data_root);
    }

    #[test]
    fn provisioning_an_existing_workspace_is_refused_not_reseeded() {
        let data_root = disposable_root("s15-04-existing-workspace");
        std::fs::create_dir_all(data_root.join("config")).expect("config dir");
        std::fs::write(data_root.join("config/local-runtime.json"), "{\"formatVersion\":1}")
            .expect("write registry");
        // This is a reopen, not a first run: provisioning must refuse rather
        // than overwrite the existing registry.
        let controller =
            LifecycleController::new(Some(nonexistent_paths(&data_root)), DEFAULT_API_PORT);
        assert!(!controller.is_first_run());
        let refused = controller.provision_first_run("Replacement Name");
        assert_eq!(
            refused.err().as_deref(),
            Some("WORKSPACE_ALREADY_PROVISIONED")
        );
        let preserved =
            std::fs::read_to_string(data_root.join("config/local-runtime.json"))
                .expect("read registry");
        assert_eq!(preserved, "{\"formatVersion\":1}");
        assert!(!controller.has_supervisor());
        let _ = std::fs::remove_dir_all(&data_root);
    }

    /// Paths bound to nonexistent executables, so a provisioning call that is
    /// expected to fail must fail for the code under test, not a spawn reason.
    fn nonexistent_paths(data_root: &std::path::Path) -> LifecyclePaths {
        LifecyclePaths {
            python_exe: std::path::PathBuf::from("C:/nonexistent/python.exe"),
            launcher_script: std::path::PathBuf::from("C:/nonexistent/projecta_local.py"),
            package_root: std::path::PathBuf::from("C:/nonexistent"),
            data_root: data_root.to_path_buf(),
        }
    }

    /// A fresh, uniquely named directory under the OS temp root.
    fn disposable_root(label: &str) -> std::path::PathBuf {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|elapsed| elapsed.as_nanos())
            .unwrap_or(0);
        let root = std::env::temp_dir().join(format!("{label}-{unique}"));
        std::fs::create_dir_all(&root).expect("disposable root");
        root
    }
}
