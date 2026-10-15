// Projecta S15-03/05 lifecycle bridge: app-owned supervisor child + same-window
// runtime-control surface.
//
// The desktop owns exactly one supervisor tree: it spawns the packaged frozen
// `ProjectaLocal.exe start` child.
// Graceful stop atomically writes the manager's existing `stop.json` protocol
// only after the shared status still matches this exact child PID and fresh
// runtime ID; the manager consumes only its own ID. The SAME main window
// navigates between the locally bundled bootstrap surface and loopback SPA on
// real readiness. Second launch refuses via the supervisor lock (no second
// tree/TDB2 writer); no retry loop, no Rust process manager, no new Tauri
// command surface, no hidden background service.
//
// S15-05 adds the runtime-control surface in that same window: the durable
// lifecycle states of contract §2.1 (`bootstrap`, `starting`, `ready`,
// `degraded`, `stopped`, `failed`, `shutdown-failed`) are presented with
// Start/Stop controls, bounded user-initiated recovery, and sanitized
// diagnostics that carry the supervisor's finite failure code and failing
// service name, attributed only after runtimeId/managerPid match this child.
// No state is inferred, no failure is suppressed, and no automatic recovery
// is performed by this layer.
//
// S15-07 UX revision: one workspace-management surface carries the real
// initialization steps, the inline create card, and the runtime controls, and
// a distinct startup overlay (same document, same design tokens, no script)
// covers that surface while an action the user started is really in flight —
// the accepted `provision` request (creating the workspace record) or the
// owned runtime startup. The accepted create is marked in flight
// synchronously and runs on a worker, so the window renders the overlay for
// that action instead of blocking on a request; the overlay disappears on real
// readiness, and on every terminal outcome the management surface — failure
// banner, diagnostics, recovery, and the create card — is reachable again.

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

/// Bounded wait for the owned `provision` child during in-window workspace
/// creation. Single attempt: the bound exists so a wedged child cannot hold the
/// window forever, and it is never retried automatically.
pub const PROVISION_DEADLINE: Duration = Duration::from_secs(120);

/// Short bound for one liveness probe against a fixed loopback port. A closed
/// port refuses immediately; the bound only covers a wedged listener.
const LISTEN_PROBE_TIMEOUT: Duration = Duration::from_millis(400);

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
/// lifecycle navigation (form actions, meta refresh, readiness transition)
/// uses this exact workaround origin, which `is_allowed_navigation` already
/// permits on its default port without credentials.
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

/// Outcome of a surface Stop: either the owned tree reached `stopped`, or the
/// manager is alive and waiting for the contract's explicit stop retry.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StopOutcome {
    Stopped,
    ShutdownFailed,
}

/// Owned supervisor process tree for the packaged `ProjectaLocal.exe start`.
/// The desktop adopts only a fresh runtime identity from the exact launched
/// process or its direct one-file worker proven in that launch's job.
#[derive(Debug, Clone, PartialEq, Eq)]
struct RuntimeIdentity {
    runtime_id: String,
    manager_pid: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum StopRequestError {
    IdentityChanged,
    WriteFailed,
}

impl StopRequestError {
    fn failure_code(self) -> &'static str {
        match self {
            StopRequestError::IdentityChanged => "RUNTIME_IDENTITY_CHANGED",
            StopRequestError::WriteFailed => "STOP_REQUEST_FAILED",
        }
    }
}

/// Owned supervisor process tree: the running packaged `ProjectaLocal.exe
/// start` and, for a frozen one-file build, its worker process. Shutdown is
/// permitted only after this owned tree publishes a fresh supervisor identity;
/// the direct child handle remains safe to terminate as this instance's process.
pub struct OwnedSupervisor {
    child: Child,
    stderr: Option<ChildStderr>,
    previous_runtime_id: Option<String>,
    runtime_identity: Option<RuntimeIdentity>,
    _job: JobGuard,
    #[cfg(windows)]
    worker_image_buffer: Vec<u16>,
}

impl OwnedSupervisor {
    /// Spawn the owned, packaged frozen supervisor child.
    ///
    /// The packaged `ProjectaLocal.exe` carries the release trust anchor. Bind
    /// its frozen `LOCALAPPDATA\\Projecta` resolution to the data root already
    /// selected by `LifecyclePaths`; do not invoke the source Python script,
    /// which has no embedded release-verification key.
    pub fn spawn(
        supervisor_exe: &std::path::Path,
        local_app_data: &std::path::Path,
        previous_runtime_id: Option<String>,
    ) -> std::io::Result<Self> {
        let mut command = Command::new(supervisor_exe);
        command
            .arg("start")
            .env_remove("PROJECTA_LAUNCHER_PACKAGE_ROOT")
            .env_remove("PROJECTA_LAUNCHER_DATA_ROOT")
            .env("LOCALAPPDATA", local_app_data)
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
        let job = match JobGuard::assign(raw_handle) {
            Ok(job) => job,
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(error);
            }
        };
        Ok(Self {
            child,
            stderr,
            previous_runtime_id,
            runtime_identity: None,
            _job: job,
            #[cfg(windows)]
            worker_image_buffer: vec![0_u16; 32_768],
        })
    }

    /// Owned child PID (diagnostics only; never used to manage foreign PIDs).
    #[must_use]
    pub fn pid(&self) -> u32 {
        self.child.id()
    }

    fn owns_manager_process(&mut self, manager_pid: u32, expected_exe: &std::path::Path) -> bool {
        if manager_pid == self.pid() {
            return true;
        }
        #[cfg(windows)]
        {
            return self._job.contains_supervisor_process(
                manager_pid,
                self.pid(),
                expected_exe,
                &mut self.worker_image_buffer,
            );
        }
        #[cfg(not(windows))]
        {
            let _ = expected_exe;
            false
        }
    }

    /// Adopt the supervisor identity only after this process tree publishes a
    /// fresh runtime record. The manager must be this exact child, or its
    /// active, direct frozen worker in the same kill-on-close job with the
    /// exact packaged image; other job members and descendants are insufficient.
    fn observe_runtime_identity(&mut self, paths: &LifecyclePaths) -> bool {
        if self.runtime_identity.is_some() {
            return true;
        }
        if !self.is_running() {
            return false;
        }
        let Some(status) = paths.read_runtime_status() else {
            return false;
        };
        let (Some(runtime_id), Some(manager_pid)) = (status.runtime_id, status.manager_pid) else {
            return false;
        };
        if status.state.is_none()
            || !self.owns_manager_process(manager_pid, &paths.supervisor_exe)
            || self.previous_runtime_id.as_deref() == Some(runtime_id.as_str())
        {
            return false;
        }
        self.runtime_identity = Some(RuntimeIdentity {
            runtime_id,
            manager_pid,
        });
        true
    }

    fn runtime_identity(&self) -> Option<&RuntimeIdentity> {
        self.runtime_identity.as_ref()
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

/// Windows Job Object with kill-on-close for the owned supervisor child.
/// Graceful stop still uses the manager's runtimeId-matched `stop.json`
/// protocol. A failed setup rejects the child instead of running uncontained.
struct JobGuard {
    #[allow(dead_code)]
    handle: isize,
}
#[cfg(windows)]
#[allow(dead_code)]
#[repr(C)]
struct ProcessEntry32W {
    size: u32,
    usage: u32,
    process_id: u32,
    default_heap_id: usize,
    module_id: u32,
    thread_count: u32,
    parent_process_id: u32,
    base_priority: i32,
    flags: u32,
    executable_name: [u16; 260],
}

#[cfg(windows)]
fn process_has_parent(process_id: u32, expected_parent_id: u32) -> bool {
    const TH32CS_SNAPPROCESS: u32 = 0x0000_0002;
    let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) };
    if snapshot == 0 || snapshot == -1 {
        return false;
    }
    let mut entry: ProcessEntry32W = unsafe { std::mem::zeroed() };
    entry.size = std::mem::size_of::<ProcessEntry32W>() as u32;
    let mut found_parent = false;
    let mut has_entry = unsafe { Process32FirstW(snapshot, &mut entry) } != 0;
    while has_entry {
        if entry.process_id == process_id {
            found_parent = entry.parent_process_id == expected_parent_id;
            break;
        }
        has_entry = unsafe { Process32NextW(snapshot, &mut entry) } != 0;
    }
    unsafe {
        CloseHandle(snapshot);
    }
    found_parent
}

impl JobGuard {
    #[cfg(windows)]
    fn assign(process: isize) -> std::io::Result<Self> {
        unsafe { create_kill_on_close_job(process) }
            .map(|handle| Self { handle })
            .map_err(|failure| {
                std::io::Error::new(
                    std::io::ErrorKind::Other,
                    format!("supervisor Job Object setup failed: {failure:?}"),
                )
            })
    }

    #[cfg(all(windows, test))]
    fn contains_process(&self, pid: u32) -> JobMembership {
        const PROCESS_QUERY_INFORMATION: u32 = 0x0000_0400;
        const PROCESS_QUERY_LIMITED_INFORMATION: u32 = 0x0000_1000;
        if self.handle == 0 {
            return JobMembership::NoJob;
        }
        let process = unsafe {
            OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION,
                0,
                pid,
            )
        };
        if process == 0 {
            return JobMembership::OpenFailed(unsafe { GetLastError() });
        }
        let mut in_job = 0_i32;
        let queried = unsafe { IsProcessInJob(process, self.handle, &mut in_job) };
        let error = if queried == 0 {
            unsafe { GetLastError() }
        } else {
            0
        };
        unsafe {
            CloseHandle(process);
        }
        if queried == 0 {
            JobMembership::QueryFailed(error)
        } else {
            JobMembership::InJob(in_job != 0)
        }
    }
    #[cfg(windows)]
    fn contains_supervisor_process(
        &self,
        pid: u32,
        launch_pid: u32,
        expected_exe: &std::path::Path,
        image_buffer: &mut [u16],
    ) -> bool {
        const PROCESS_QUERY_INFORMATION: u32 = 0x0000_0400;
        const PROCESS_QUERY_LIMITED_INFORMATION: u32 = 0x0000_1000;
        const SYNCHRONIZE: u32 = 0x0010_0000;
        const WAIT_TIMEOUT: u32 = 0x0000_0102;
        if self.handle == 0 || image_buffer.is_empty() {
            return false;
        }
        let process = unsafe {
            OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
                0,
                pid,
            )
        };
        if process == 0 {
            return false;
        }
        let mut in_job = 0_i32;
        let in_owned_job =
            unsafe { IsProcessInJob(process, self.handle, &mut in_job) } != 0 && in_job != 0;
        let running = unsafe { WaitForSingleObject(process, 0) } == WAIT_TIMEOUT;
        let direct_worker = in_owned_job && running && process_has_parent(pid, launch_pid);
        let mut image_len = image_buffer.len() as u32;
        let image_queried = direct_worker
            && unsafe {
                QueryFullProcessImageNameW(
                    process,
                    0,
                    image_buffer.as_mut_ptr(),
                    &mut image_len,
                )
            } != 0;
        let still_running = unsafe { WaitForSingleObject(process, 0) } == WAIT_TIMEOUT;
        unsafe {
            CloseHandle(process);
        }
        if !image_queried
            || !still_running
            || image_len == 0
            || image_len as usize > image_buffer.len()
        {
            return false;
        }
        let image_len = image_len as usize;
        let image_len = if image_buffer[image_len - 1] == 0 {
            image_len - 1
        } else {
            image_len
        };
        if image_len == 0 {
            return false;
        }
        use std::os::windows::ffi::OsStringExt as _;
        let image_path = std::path::PathBuf::from(std::ffi::OsString::from_wide(
            &image_buffer[..image_len],
        ));
        let (Ok(image_path), Ok(expected_exe)) = (
            std::fs::canonicalize(image_path),
            std::fs::canonicalize(expected_exe),
        ) else {
            return false;
        };
        image_path
            .to_string_lossy()
            .eq_ignore_ascii_case(&expected_exe.to_string_lossy())
    }
}

#[cfg(all(windows, test))]
#[derive(Debug, PartialEq, Eq)]
enum JobMembership {
    NoJob,
    OpenFailed(u32),
    QueryFailed(u32),
    InJob(bool),
}

impl JobGuard {
    #[cfg(not(windows))]
    fn assign(_process: isize) -> std::io::Result<Self> {
        Ok(Self { handle: 0 })
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
    min_working_set: usize,
    max_working_set: usize,
    active_process_limit: u32,
    affinity: usize,
    priority_class: u32,
    scheduling_class: u32,
}

#[cfg(windows)]
#[repr(C)]
struct JobIoCounters {
    read_operation_count: i64,
    write_operation_count: i64,
    other_operation_count: i64,
    read_transfer_count: i64,
    write_transfer_count: i64,
    other_transfer_count: i64,
}

#[cfg(windows)]
#[repr(C)]
struct JobExtendedLimits {
    basic: JobBasicLimits,
    io_counters: JobIoCounters,
    process_memory_limit: usize,
    job_memory_limit: usize,
    peak_process_memory_used: usize,
    peak_job_memory_used: usize,
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
    unsafe fn MoveFileExW(existing: *const u16, new: *const u16, flags: u32) -> i32;
    unsafe fn OpenProcess(access: u32, inherit: i32, pid: u32) -> isize;
    unsafe fn IsProcessInJob(process: isize, job: isize, result: *mut i32) -> i32;
    unsafe fn QueryFullProcessImageNameW(
        process: isize,
        flags: u32,
        image_name: *mut u16,
        size: *mut u32,
    ) -> i32;
    unsafe fn WaitForSingleObject(handle: isize, milliseconds: u32) -> u32;
    unsafe fn CreateToolhelp32Snapshot(flags: u32, process_id: u32) -> isize;
    unsafe fn Process32FirstW(snapshot: isize, entry: *mut ProcessEntry32W) -> i32;
    unsafe fn Process32NextW(snapshot: isize, entry: *mut ProcessEntry32W) -> i32;
    #[cfg(test)]
    unsafe fn TerminateProcess(process: isize, exit_code: u32) -> i32;
    #[cfg(windows)]
    unsafe fn GetLastError() -> u32;
}

#[cfg(windows)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum JobSetupFailure {
    InvalidProcess,
    Create(u32),
    Configure(u32),
    Assign(u32),
}
/// Create a kill-on-close job and assign exactly one owned child process.
/// Returns the failing Win32 stage and immediately captured error code.
/// Configure KILL_ON_JOB_CLOSE through the extended-limit information class.
#[cfg(windows)]
unsafe fn create_kill_on_close_job(process: isize) -> Result<isize, JobSetupFailure> {
    const JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: i32 = 9;
    const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: u32 = 0x0000_2000;
    if process == 0 {
        return Err(JobSetupFailure::InvalidProcess);
    }
    unsafe {
        let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
        if job == 0 {
            let error = GetLastError();
            return Err(JobSetupFailure::Create(error));
        }
        let mut limits: JobExtendedLimits = std::mem::zeroed();
        limits.basic.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let applied = SetInformationJobObject(
            job,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            std::ptr::addr_of!(limits).cast(),
            std::mem::size_of::<JobExtendedLimits>() as u32,
        );
        if applied == 0 {
            let error = GetLastError();
            CloseHandle(job);
            return Err(JobSetupFailure::Configure(error));
        }
        if AssignProcessToJobObject(job, process) == 0 {
            let error = GetLastError();
            CloseHandle(job);
            return Err(JobSetupFailure::Assign(error));
        }
        Ok(job)
    }
}
#[cfg(windows)]
fn atomic_replace_file(source: &std::path::Path, destination: &std::path::Path) -> std::io::Result<()> {
    use std::os::windows::ffi::OsStrExt as _;
    const MOVEFILE_REPLACE_EXISTING: u32 = 0x0000_0001;
    const MOVEFILE_WRITE_THROUGH: u32 = 0x0000_0008;
    let source_wide = source
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect::<Vec<_>>();
    let destination_wide = destination
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect::<Vec<_>>();
    let moved = unsafe {
        MoveFileExW(
            source_wide.as_ptr(),
            destination_wide.as_ptr(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
        )
    };
    if moved == 0 {
        Err(std::io::Error::last_os_error())
    } else {
        Ok(())
    }
}

#[cfg(not(windows))]
fn atomic_replace_file(source: &std::path::Path, destination: &std::path::Path) -> std::io::Result<()> {
    std::fs::rename(source, destination)
}

/// Extract the trailing `[CODE]` failure token from supervisor stderr.
fn extract_failure_code(stderr: &str) -> Option<String> {
    let open = stderr.rfind('[')?;
    let rest = &stderr[open + 1..];
    let close = rest.find(']')?;
    let code = &rest[..close];
    is_finite_code(code).then(|| code.to_string())
}

/// Map a failed `provision` child's stderr to a finite refusal code.
///
/// The launcher's own trailing `[CODE]` token wins; otherwise a packaged
/// launcher built before the `provision` subcommand existed is reported as the
/// finite, actionable `FIRST_RUN_UNSUPPORTED_PACKAGE` code, and anything else
/// degrades to `PROVISION_FAILED`. No raw stderr text ever leaves this
/// function.
#[must_use]
fn provision_failure_code(stderr: &str) -> String {
    extract_failure_code(stderr).unwrap_or_else(|| {
        if stderr.contains("invalid choice") || stderr.contains("COMMAND_INVALID") {
            "FIRST_RUN_UNSUPPORTED_PACKAGE".to_string()
        } else {
            "PROVISION_FAILED".to_string()
        }
    })
}


/// What the app-owned data root says about its local workspace, as far as the
/// management surface may render it.
///
/// `Active` carries only values validated against the same finite rules the
/// Python launcher applies when it writes the record; `Unreadable` exists so a
/// malformed or unexpected document degrades to a finite statement instead of
/// rendering arbitrary content, and `Absent` is the single authoritative
/// first-run signal.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkspaceRecord {
    Absent,
    Active { name: String, project_id: String },
    Unreadable,
}
/// User-selected color scheme mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ThemeMode {
    Light,
    Dark,
    System,
}

impl Default for ThemeMode {
    fn default() -> Self {
        Self::System
    }
}

impl ThemeMode {
    #[must_use]
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Light => "light",
            Self::Dark => "dark",
            Self::System => "system",
        }
    }

    #[must_use]
    pub fn from_str_loose(s: &str) -> Option<Self> {
        match s.trim().to_lowercase().as_str() {
            "light" => Some(Self::Light),
            "dark" => Some(Self::Dark),
            "system" => Some(Self::System),
            _ => None,
        }
    }
}

/// UI preferences record stored deterministically in `<data_root>/config/ui-preferences.json`.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct UiPreferences {
    #[serde(default)]
    pub theme_mode: ThemeMode,
}


/// Derive the frozen supervisor's `LOCALAPPDATA` parent only for its supported
/// `<LOCALAPPDATA>/Projecta` data-root layout.
fn local_app_data_for_projecta_root(
    data_root: &std::path::Path,
) -> Option<&std::path::Path> {
    if data_root.file_name()? != std::ffi::OsStr::new("Projecta") {
        return None;
    }
    data_root.parent()
}

/// Resolve lifecycle paths from the environment, falling back to the packaged
/// sibling layout next to the running executable.
///
/// - `PROJECTA_DESKTOP_PACKAGE_ROOT` + `PROJECTA_LAUNCHER_DATA_ROOT` points
///   at a staged/bundled tree containing `<root>/ProjectaLocal.exe`; the data
///   root must be exactly `<task LOCALAPPDATA>/Projecta`.
/// - Otherwise the sibling `ProjectaLocal.exe` beside the desktop executable
///   uses the per-user `%LOCALAPPDATA%/Projecta` data root.
#[derive(Debug, Clone)]
pub struct LifecyclePaths {
    pub supervisor_exe: std::path::PathBuf,
    pub local_app_data: std::path::PathBuf,
    pub data_root: std::path::PathBuf,
}

impl LifecyclePaths {
    /// Resolve from environment/sibling layout; `None` when the packaged
    /// frozen supervisor and its supported data-root layout are unavailable.
    #[must_use]
    pub fn resolve() -> Option<Self> {
        if let (Some(package_root), Some(data_root)) = (
            std::env::var_os("PROJECTA_DESKTOP_PACKAGE_ROOT").map(std::path::PathBuf::from),
            std::env::var_os("PROJECTA_LAUNCHER_DATA_ROOT").map(std::path::PathBuf::from),
        ) {
            let local_app_data = local_app_data_for_projecta_root(&data_root)?.to_path_buf();
            let supervisor_exe = package_root.join("ProjectaLocal.exe");
            if supervisor_exe.is_file() {
                return Some(Self {
                    supervisor_exe,
                    local_app_data,
                    data_root,
                });
            }
            return None;
        }
        let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
        let local_app_data = std::env::var_os("LOCALAPPDATA").map(std::path::PathBuf::from)?;
        let data_root = local_app_data.join("Projecta");
        let supervisor_exe = exe_dir.join("ProjectaLocal.exe");
        if supervisor_exe.is_file() {
            return Some(Self {
                supervisor_exe,
                local_app_data,
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
    /// UI preferences record marker inside the data root: `config/ui-preferences.json`.
    #[must_use]
    pub fn preferences_config_path(&self) -> std::path::PathBuf {
        self.data_root.join("config/ui-preferences.json")
    }

    /// Read the UI preferences persisted in this data root. Returns default
    /// (`ThemeMode::System`) if absent or corrupted.
    #[must_use]
    pub fn read_ui_preferences(&self) -> UiPreferences {
        let path = self.preferences_config_path();
        let Ok(text) = std::fs::read_to_string(&path) else {
            return UiPreferences::default();
        };
        serde_json::from_str(&text).unwrap_or_default()
    }

    /// Persist UI preferences in this data root. Ensures `config/` exists.
    pub fn write_ui_preferences(&self, prefs: &UiPreferences) -> std::io::Result<()> {
        let path = self.preferences_config_path();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let text = serde_json::to_string_pretty(prefs).map_err(|e| {
            std::io::Error::new(std::io::ErrorKind::InvalidData, e)
        })?;
        std::fs::write(&path, text)
    }


    /// Spawn the packaged supervisor's data-only `provision` command against
    /// this lifecycle's exact `%LOCALAPPDATA%/Projecta` root. It reuses the
    /// audited Python name validation, generated project, fixed
    /// `local-operator` actor, and DPAPI CurrentUser protection, and never
    /// performs OS installation (no package copy, Start-Menu shortcut, or
    /// registry write).
    ///
    /// The controller owns the bounded wait, single attempt, and cancellation:
    /// this is the only process the app starts for workspace creation.
    ///
    /// `stdout` is discarded and `stderr` is reduced to the supervisor's
    /// finite failure token; raw launcher output is never surfaced to WebView.
    pub fn spawn_provision(&self, workspace_name: &str) -> Result<Child, String> {
        let mut command = Command::new(&self.supervisor_exe);
        command
            .arg("provision")
            .arg("--workspace-name")
            .arg(workspace_name)
            .env_remove("PROJECTA_LAUNCHER_PACKAGE_ROOT")
            .env_remove("PROJECTA_LAUNCHER_DATA_ROOT")
            .env("LOCALAPPDATA", &self.local_app_data)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::piped());
        command
            .spawn()
            .map_err(|_| "PROVISION_SPAWN_FAILED".to_string())
    }

    /// Read the workspace record persisted in this data root
    /// (`config/local-runtime.json`, written exactly once by the launcher's
    /// `provision` on a fresh directory only).
    ///
    /// This is a read-only view of user data. Every field is validated against
    /// the finite rules the launcher applies (`formatVersion` 1, project-ID
    /// pattern, and a display name of at most 128 printable characters), so a
    /// missing or unexpected document degrades to `Absent`/`Unreadable`.
    #[must_use]
    pub fn read_workspace_record(&self) -> WorkspaceRecord {
        let path = self.workspace_config_path();
        let Ok(text) = std::fs::read_to_string(&path) else {
            return WorkspaceRecord::Absent;
        };
        let Ok(document) = serde_json::from_str::<serde_json::Value>(&text) else {
            return WorkspaceRecord::Unreadable;
        };
        let Some(object) = document.as_object() else {
            return WorkspaceRecord::Unreadable;
        };
        let project_id = object.get("projectId").and_then(serde_json::Value::as_str);
        let project_name = object.get("projectName").and_then(serde_json::Value::as_str);
        let format_ok = object.get("formatVersion").and_then(serde_json::Value::as_i64) == Some(1);
        let id_ok = project_id.is_some_and(|value| {
            !value.is_empty()
                && value.len() <= 63
                && value
                    .bytes()
                    .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
                && value
                    .bytes()
                    .next()
                    .is_some_and(|first| first.is_ascii_lowercase() || first.is_ascii_digit())
        });
        let name_ok = project_name.is_some_and(|value| {
            let trimmed = value.trim();
            !trimmed.is_empty()
                && trimmed.chars().count() <= 128
                && !trimmed.chars().any(|character| (character as u32) < 0x20)
        });
        if format_ok && id_ok && name_ok {
            return WorkspaceRecord::Active {
                project_id: project_id.unwrap_or_default().to_string(),
                name: project_name.unwrap_or_default().trim().to_string(),
            };
        }
        WorkspaceRecord::Unreadable
    }

    /// Request the existing manager's reverse-order stop protocol for one
    /// exact owned identity. Recheck status around an atomic stop-file write;
    /// the manager consumes the file only when its own runtimeId matches.
    fn request_stop(&self, identity: &RuntimeIdentity) -> Result<(), StopRequestError> {
        let matches_owner = |status: Option<RuntimeStatusSnapshot>| {
            status.is_some_and(|status| {
                status.runtime_id.as_deref() == Some(identity.runtime_id.as_str())
                    && status.manager_pid == Some(identity.manager_pid)
            })
        };
        if !matches_owner(self.read_runtime_status()) {
            return Err(StopRequestError::IdentityChanged);
        }
        let state_dir = self.data_root.join("state");
        let stop_path = state_dir.join("stop.json");
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let temporary = state_dir.join(format!(
            "stop.json.{}.{}.tmp",
            identity.manager_pid, nonce
        ));
        let content = serde_json::json!({"runtimeId": identity.runtime_id.as_str()}).to_string();
        let mut file = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .map_err(|_| StopRequestError::WriteFailed)?;
        use std::io::Write as _;
        if file.write_all(content.as_bytes()).is_err() || file.sync_all().is_err() {
            drop(file);
            let _ = std::fs::remove_file(&temporary);
            return Err(StopRequestError::WriteFailed);
        }
        drop(file);
        if !matches_owner(self.read_runtime_status()) {
            let _ = std::fs::remove_file(&temporary);
            return Err(StopRequestError::IdentityChanged);
        }
        if atomic_replace_file(&temporary, &stop_path).is_err() {
            let _ = std::fs::remove_file(&temporary);
            return Err(StopRequestError::WriteFailed);
        }
        Ok(())
    }

    /// Read the shared data-root status document (`state/runtime.json`) and
    /// return only its sanitized lifecycle view. The caller must bind any
    /// ownership decision to runtimeId plus managerPid on its exact live child;
    /// this document alone never proves that this window owns the service tree.
    #[must_use]
    pub fn read_runtime_status(&self) -> Option<RuntimeStatusSnapshot> {
        let path = self.data_root.join("state/runtime.json");
        let text = std::fs::read_to_string(&path).ok()?;
        let document: serde_json::Value = serde_json::from_str(&text).ok()?;
        let object = document.as_object()?;
        let runtime_id = object
            .get("runtimeId")
            .and_then(serde_json::Value::as_str)
            .filter(|value| {
                value.len() == 32
                    && value
                        .bytes()
                        .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
            })
            .map(str::to_string);
        let manager_pid = object
            .get("managerPid")
            .and_then(serde_json::Value::as_u64)
            .and_then(|pid| u32::try_from(pid).ok())
            .filter(|pid| *pid > 0);
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
        Some(RuntimeStatusSnapshot {
            runtime_id,
            manager_pid,
            state,
            failure,
        })
    }
}

/// Sanitized lifecycle view of the owned manager's status document.
#[derive(Debug, Clone)]
pub struct RuntimeStatusSnapshot {
    pub runtime_id: Option<String>,
    pub manager_pid: Option<u32>,
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

/// Sanitized view of one `GET /health/ready` response.
///
/// Every field is reduced to an allowlisted word or a finite code token, so the
/// management surface can name the dependency that is not ready yet without
/// ever rendering arbitrary response content: `semantic_core`/`oidc` are the
/// API's own published readiness fields and `reason_code` is its finite
/// `reasonCode` token.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ApiReadiness {
    pub http_status: Option<u16>,
    pub status: Option<String>,
    pub semantic_core: Option<String>,
    pub oidc: Option<String>,
    pub reason_code: Option<String>,
}

/// Keep a response value only when it is one of the words the API publishes.
#[must_use]
fn allowed_word(value: Option<&str>, allowed: &[&str]) -> Option<String> {
    value
        .filter(|candidate| allowed.contains(candidate))
        .map(str::to_string)
}

/// Whether something is accepting connections on `port` right now.
///
/// A plain connect probe: it never binds, so it cannot collide with a service
/// that is still claiming its own port during startup, and it never sends any
/// application data. It observes exactly "this port answered", which is the
/// real signal the startup surface needs.
#[must_use]
pub fn service_listening(port: u16, timeout: Duration) -> bool {
    let address = format!("{LOOPBACK_HOST}:{port}");
    std::net::TcpStream::connect_timeout(
        &address.parse().unwrap_or("127.0.0.1:1".parse().unwrap()),
        timeout,
    )
    .is_ok()
}

/// Probe `GET /health/ready` on the owned loopback API and return its sanitized
/// readiness view: HTTP status plus the API's own `status`/`semanticCore`/
/// `oidc`/`reasonCode` fields when the body carries them.
///
/// Single attempt, no retry loop: the caller decides cadence and the overall
/// startup deadline. A transport error yields a view with no status; a partial
/// or unparseable body yields no fields rather than an invented success.
#[must_use]
pub fn probe_api_readiness(api_port: u16, timeout: Duration) -> ApiReadiness {
    let address = format!("{LOOPBACK_HOST}:{api_port}");
    let Ok(mut stream) = std::net::TcpStream::connect_timeout(
        &address.parse().unwrap_or("127.0.0.1:1".parse().unwrap()),
        timeout,
    ) else {
        return ApiReadiness::default();
    };
    let _ = stream.set_read_timeout(Some(timeout));
    let _ = stream.set_write_timeout(Some(timeout));
    let request = format!(
        "GET /health/ready HTTP/1.1\r\nHost: {LOOPBACK_HOST}:{api_port}\r\nConnection: close\r\n\r\n"
    );
    if std::io::Write::write_all(&mut stream, request.as_bytes()).is_err() {
        return ApiReadiness::default();
    }
    // The readiness document is tiny; bound the read and accept whatever
    // arrived when the socket closes or the short timeout expires.
    let mut raw = Vec::with_capacity(1024);
    let mut chunk = [0u8; 512];
    while raw.len() < 8192 {
        match std::io::Read::read(&mut stream, &mut chunk) {
            Ok(0) => break,
            Ok(read) => raw.extend_from_slice(&chunk[..read]),
            Err(_) => break,
        }
    }
    let text = String::from_utf8_lossy(&raw);
    let (head, body) = match text.split_once("\r\n\r\n") {
        Some((head, body)) => (head, body),
        None => (text.as_ref(), ""),
    };
    let http_status = head
        .lines()
        .next()
        .filter(|line| line.starts_with("HTTP/"))
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|code| code.parse::<u16>().ok());
    let document: Option<serde_json::Value> = serde_json::from_str(body).ok();
    let field = |key: &str| {
        document
            .as_ref()
            .and_then(serde_json::Value::as_object)
            .and_then(|object| object.get(key))
            .and_then(serde_json::Value::as_str)
    };
    ApiReadiness {
        http_status,
        status: allowed_word(field("status"), &["ready", "not-ready"]),
        semantic_core: allowed_word(field("semanticCore"), &["ready", "unavailable"]),
        oidc: allowed_word(field("oidc"), &["ready", "unavailable"]),
        reason_code: field("reasonCode")
            .filter(|code| is_finite_code(code))
            .map(str::to_string),
    }
}

/// Poll `GET /health/ready` on the owned loopback API with a short timeout.
///
/// Single attempt, no retry loop: the caller decides cadence and the overall
/// startup deadline. Only HTTP 200 counts as ready; every other status or a
/// transport error is `NotReady`/`ProbeFailed`.
#[must_use]
pub fn poll_api_ready(api_port: u16, timeout: Duration) -> Readiness {
    match probe_api_readiness(api_port, timeout).http_status {
        Some(200) => Readiness::Ready,
        Some(_) => Readiness::NotReady,
        None => Readiness::ProbeFailed,
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

/// Initial URL of the privileged main window: exactly the bundled bootstrap
/// surface, parsed so a malformed target fails at startup instead of at first
/// render. The window never opens an external origin.
#[must_use]
pub fn main_window_url() -> Url {
    Url::parse(bootstrap_url().as_str()).expect("valid bundled bootstrap URL")
}

/// Whether the privileged main view may open a NEW window for `url`.
///
/// Never. A secondary window would render content outside the single-window
/// contract and outside the navigation guard this view applies, so every
/// `window.open`-style request is denied in the main view. An explicit
/// external-link request is handed to the system browser instead (S15-07,
/// `external_link_allowed`), not to a second privileged window.
#[must_use]
pub fn new_window_allowed(_url: &Url) -> bool {
    false
}

/// Whether a new-window request from the privileged view is an allowed
/// EXTERNAL link, which MAY be opened in the system browser (desktop release
/// contract §5) instead of being rendered anywhere inside the app.
///
/// Exactly absolute web URLs qualify — `http` and `https` with a host — because
/// those are the destinations a user can recognize and that the system browser
/// can own. Third-party origins and foreign loopback ports both qualify: the
/// privileged view refuses to navigate to them, and the system browser is the
/// explicit hand-off. Every other scheme (`file:`, `data:`, `javascript:`,
/// app custom schemes, relative URLs) is not an external link and is refused;
/// nothing is ever opened without a host decision, and this action never
/// renders third-party content inside the privileged view.
#[must_use]
pub fn external_link_allowed(url: &Url) -> bool {
    matches!(url.scheme(), "http" | "https") && url.host_str().is_some()
}

/// Open `url` in the user's system browser (the default protocol handler),
/// returning whether the launch was accepted.
///
/// This is the desktop replacement for `webbrowser.open`: an explicit
/// external-link request from the privileged view is handed to the operating
/// system instead of navigating the WebView. Only the URL is passed to the
/// shell; no file, no working directory, no arguments, and no additional
/// privilege. Nothing is logged, so a URL that carries user data can never
/// reach a log file.
#[cfg(windows)]
pub fn open_in_system_browser(url: &Url) -> bool {
    /// How the shell shows a launched URL (normal window/tab).
    const SW_SHOWNORMAL: i32 = 1;
    /// ShellExecuteW reports success as a value greater than 32.
    const SE_ERR_SUCCESS_THRESHOLD: isize = 32;

    #[link(name = "shell32")]
    unsafe extern "system" {
        unsafe fn ShellExecuteW(
            window: *const std::ffi::c_void,
            operation: *const u16,
            file: *const u16,
            parameters: *const u16,
            directory: *const u16,
            show_command: i32,
        ) -> *const std::ffi::c_void;
    }

    #[cfg(windows)]
    fn wide(value: &str) -> Vec<u16> {
        use std::os::windows::ffi::OsStrExt as _;
        std::ffi::OsStr::new(value)
            .encode_wide()
            .chain(std::iter::once(0))
            .collect()
    }

    let operation = wide("open");
    let file = wide(url.as_str());
    let result = unsafe {
        ShellExecuteW(
            std::ptr::null(),
            operation.as_ptr(),
            file.as_ptr(),
            std::ptr::null(),
            std::ptr::null(),
            SW_SHOWNORMAL,
        )
    };
    result as isize > SE_ERR_SUCCESS_THRESHOLD
}

/// Non-Windows builds have no desktop shell contract in this release; the
/// external-link hand-off simply refuses rather than guessing.
#[cfg(not(windows))]
pub fn open_in_system_browser(_url: &Url) -> bool {
    false
}

/// Optional absolute download directory requested through the environment
/// (`PROJECTA_DESKTOP_DOWNLOAD_DIR`).
///
/// The app otherwise keeps the platform's default download destination, exactly
/// like the previous system-browser experience. A relative or empty value is
/// ignored rather than silently rewriting where a user's archive lands.
#[must_use]
pub fn download_directory() -> Option<std::path::PathBuf> {
    std::env::var("PROJECTA_DESKTOP_DOWNLOAD_DIR")
        .ok()
        .as_deref()
        .and_then(absolute_directory)
}

/// Keep only absolute directories; anything else is not a destination the host
/// is allowed to invent.
#[must_use]
pub fn absolute_directory(raw: &str) -> Option<std::path::PathBuf> {
    let path = std::path::PathBuf::from(raw);
    path.is_absolute().then_some(path)
}

/// Resolve where a requested download is written.
///
/// The portable-export archive reaches the window as a same-origin blob
/// download; `default` is the destination the platform already chose (its
/// download folder plus the name the page requested). The file name is always
/// preserved — the host never renames or invents an archive name. When an
/// absolute `PROJECTA_DESKTOP_DOWNLOAD_DIR` is set (disposable proof root, the
/// same mechanism as the other disposable roots this host already honours), the
/// destination moves there; a directory that cannot be created leaves the
/// platform destination untouched instead of failing the download.
#[must_use]
pub fn download_destination(
    default: &std::path::Path,
    override_directory: Option<&std::path::Path>,
) -> Option<std::path::PathBuf> {
    let name = default.file_name()?;
    let directory = override_directory?;
    if std::fs::create_dir_all(directory).is_err() {
        return None;
    }
    Some(directory.join(name))
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

/// Status of one real initialization step.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StepStatus {
    Pending,
    Active,
    Done,
    Failed,
}

impl StepStatus {
    /// Badge class plus label for the surface. The label carries a shape/text
    /// prefix so the state is never encoded by color alone.
    #[must_use]
    fn badge(self) -> (&'static str, &'static str) {
        match self {
            StepStatus::Done => ("step-done", "\u{2713} Done"),
            StepStatus::Active => ("step-active", "\u{25cf} In progress"),
            StepStatus::Pending => ("step-pending", "\u{25cb} Waiting"),
            StepStatus::Failed => ("step-failed", "\u{2715} Failed"),
        }
    }
}

/// One initialization step of the workspace-management surface. `key` is the
/// supervisor's own service name for service steps (so a failure record maps
/// onto it directly) and a stable surface key otherwise.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InitStep {
    pub key: &'static str,
    pub label: &'static str,
    pub target: String,
    pub status: StepStatus,
}

/// Finite supervisor-level codes: the owned manager itself did not come up (as
/// opposed to one of its service dependencies failing).
const SUPERVISOR_FAILURE_CODES: [&str; 6] = [
    "SUPERVISOR_SPAWN_FAILED",
    "SUPERVISOR_EXITED",
    "RUNTIME_ALREADY_ACTIVE",
    "PLATFORM_UNSUPPORTED",
    "ALREADY_STARTED",
    "RUNTIME_INTERNAL_ERROR",
];

/// Real observations the step list is derived from.
///
/// Every field is something this process actually measured on this machine:
/// whether the bundled package resolved, whether the owned supervisor child is
/// alive, whether each fixed loopback port answered, and what the API's own
/// `/health/ready` document says. Nothing here is projected over time, sampled
/// on a timer, or invented to look like progress.
#[derive(Debug, Clone, Default)]
pub struct InitObservations {
    pub package_resolved: bool,
    pub supervisor_alive: bool,
    pub postgres_listening: bool,
    pub fuseki_listening: bool,
    pub semantic_listening: bool,
    pub api_listening: bool,
    pub api_readiness: ApiReadiness,
}

/// Build the eight real initialization steps in the supervisor's own start
/// order: package → supervisor → PostgreSQL → Fuseki → Semantic Core → API →
/// core readiness → session/auth readiness.
///
/// `Active` marks the step the current startup attempt is working on: the first
/// not-yet-observed entry of that ordered list. A recorded failure marks its
/// own step `Failed` instead of hiding the code behind an empty success.
#[must_use]
pub fn build_init_steps(
    state: LifecycleState,
    failure: Option<&FailureRecord>,
    observations: &InitObservations,
) -> Vec<InitStep> {
    let ready = state == LifecycleState::Ready;
    let starting = matches!(state, LifecycleState::Starting);
    let code = failure.map(|record| record.code.as_str());
    let failed_service = failure.and_then(|record| record.service.as_deref());
    let service_failed = |key: &str| {
        failed_service == Some(key)
            && matches!(
                code,
                Some("PORT_IN_USE") | Some("SERVICE_READINESS_TIMEOUT") | Some("SERVICE_BECAME_UNREADY")
            )
    };
    let supervisor_failed = code.is_some_and(|code| SUPERVISOR_FAILURE_CODES.contains(&code));

    let mut steps = Vec::with_capacity(8);
    steps.push(InitStep {
        key: "package",
        label: "Application package",
        target: "Local package manifest".to_string(),
        status: if observations.package_resolved {
            StepStatus::Done
        } else {
            StepStatus::Failed
        },
    });
    steps.push(InitStep {
        key: "supervisor",
        label: "Supervisor process",
        target: "Owned child process".to_string(),
        status: if supervisor_failed {
            StepStatus::Failed
        } else if observations.supervisor_alive || ready {
            StepStatus::Done
        } else if starting {
            StepStatus::Active
        } else {
            StepStatus::Pending
        },
    });

    let services: [(&'static str, &'static str, &'static str, bool); 4] = [
        (
            "postgres",
            "Local datastore",
            "PostgreSQL \u{00b7} port 15432",
            observations.postgres_listening,
        ),
        (
            "fuseki",
            "Knowledge triple store",
            "Fuseki \u{00b7} port 18303",
            observations.fuseki_listening,
        ),
        (
            "semanticCore",
            "Semantic Core engine",
            "Semantic Core \u{00b7} port 18080",
            observations.semantic_listening,
        ),
        (
            "api",
            "Application API",
            "API gateway \u{00b7} port 18732",
            observations.api_listening,
        ),
    ];
    let mut active_taken = false;
    for (key, label, target, listening) in services {
        let done = ready || listening;
        let status = if service_failed(key) {
            StepStatus::Failed
        } else if done {
            StepStatus::Done
        } else if starting && !active_taken {
            // Ordered start: the first dependency that is not up yet is the one
            // the supervisor is working on now.
            active_taken = true;
            StepStatus::Active
        } else {
            StepStatus::Pending
        };
        steps.push(InitStep {
            key,
            label,
            target: target.to_string(),
            status,
        });
    }

    let readiness_reason = observations.api_readiness.reason_code.clone();
    let readiness_step = |key: &'static str,
                          label: &'static str,
                          probe: &str,
                          field_ready: bool,
                          reason_failed: bool| {
        let mut target = format!("/health/ready \u{00b7} {probe}");
        if let Some(reason) = readiness_reason.as_deref() {
            target.push_str(&format!(" \u{00b7} [{reason}]"));
        }
        let status = if ready || field_ready {
            StepStatus::Done
        } else if reason_failed {
            StepStatus::Failed
        } else if observations.api_listening {
            StepStatus::Active
        } else {
            StepStatus::Pending
        };
        InitStep {
            key,
            label,
            target,
            status,
        }
    };
    steps.push(readiness_step(
        "core-readiness",
        "Core readiness probe",
        "semanticCore",
        observations.api_readiness.semantic_core.as_deref() == Some("ready"),
        matches!(
            readiness_reason.as_deref(),
            Some("SEMANTIC_CORE_CONFIGURATION_INVALID") | Some("CONFIGURATION_INVALID")
        ),
    ));
    steps.push(readiness_step(
        "auth-readiness",
        "Session and authentication probe",
        "oidc",
        observations.api_readiness.oidc.as_deref() == Some("ready"),
        matches!(
            readiness_reason.as_deref(),
            Some("OIDC_PROVIDER_UNAVAILABLE") | Some("SECRET_MANAGER_UNAVAILABLE")
        ),
    ));
    steps
}

/// The distinct startup overlay shown above the workspace-management shell
/// while an action the user started is really in flight. The overlay is a
/// plain non-modal layer of the same server-rendered document (no script, no
/// focus management): `Creating` while the owned `provision` child is writing
/// an unprovisioned data root, `Starting` while the owned runtime services are
/// starting. It disappears on real readiness (the window navigates to the
/// workspace) and on every terminal state, so the management surface — with
/// its failure banner, diagnostics, and recovery controls — becomes reachable
/// again exactly when the outcome is known.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OverlayMode {
    Creating,
    Starting,
}

/// Everything the workspace-management surface renders, built only from real
/// observations of this app's own state.
#[derive(Debug, Clone)]
pub struct ManagementView {
    pub state: LifecycleState,
    pub workspace: WorkspaceRecord,
    pub steps: Vec<InitStep>,
    pub failure: Option<FailureRecord>,
    pub api_origin: String,
    pub supervisor_pid: Option<u32>,
    pub start_pending: bool,
    pub stop_pending: bool,
    /// Whether a workspace-creation request is accepted and still in flight
    /// (the create card's own submission or the owned `provision` child it
    /// spawned). The creating overlay is shown for exactly this real state.
    pub provision_pending: bool,
    /// Whether a Start/Retry is legitimately available right now (the
    /// controller's own `can_start`).
    pub can_start: bool,
    /// Whether this process still owns an unprovisioned data root, so the
    /// inline create card is the applicable action.
    pub first_run: bool,
    /// Finite refusal code from a rejected create submission, if any.
    pub refusal: Option<String>,
    /// User-selected or system color scheme mode.
    pub theme_mode: ThemeMode,
}

impl ManagementView {
    /// Whether the surface must keep refreshing itself: a start or stop is in
    /// flight, or the app is starting (including a workspace creation in
    /// flight). Every terminal state renders statically so nothing is silently
    /// retried, and a create card that is waiting for a name is rendered
    /// without refresh so typed input is never discarded.
    #[must_use]
    pub fn is_live(&self) -> bool {
        self.start_pending
            || self.stop_pending
            || self.provision_pending
            || self.state == LifecycleState::Starting
            || (self.state == LifecycleState::Bootstrap && !self.first_run)
    }

    /// The overlay to render above the management shell, or `None` when the
    /// management surface must be fully reachable. Only the real `starting`
    /// window — a runtime start in flight, or the workspace creation that
    /// precedes it — shows an overlay; every terminal state (including a
    /// failed start) renders the management surface alone so its recovery
    /// controls and diagnostics stay usable.
    #[must_use]
    pub fn overlay(&self) -> Option<OverlayMode> {
        if self.state != LifecycleState::Starting {
            return None;
        }
        if self.provision_pending {
            Some(OverlayMode::Creating)
        } else {
            Some(OverlayMode::Starting)
        }
    }

    /// Whether the Stop/Cancel control applies: a start is in flight or an
    /// owned supervisor child exists to stop (including the manager waiting in
    /// `shutdown-failed` for its explicit stop retry).
    #[must_use]
    pub fn can_stop(&self) -> bool {
        self.state == LifecycleState::Starting || self.supervisor_pid.is_some()
    }
}

/// Static presentation layer of the management surface (tokens, layout,
/// light/dark themes). Served inline: the surface must render with no network
/// access and no script.
const SURFACE_STYLE: &str = r#"/* Projecta management surface */
:root {
  color-scheme: light dark;
  --surface-canvas: #f7f7f7;
  --surface-card: #ffffff;
  --surface-subtle: #f0f2f4;
  --surface-hover: #e9ecef;
  --surface-border: #e1e4e8;
  --surface-border-strong: #d0d5dd;
  --surface-text: #161616;
  --surface-muted: #5f6368;
  --surface-primary: #2272b4;
  --surface-primary-hover: #0e538b;
  --surface-primary-soft: rgba(34, 114, 180, 0.08);
  --surface-primary-text: #ffffff;
  --surface-danger: #c82d4c;
  --surface-danger-soft: #fff5f7;
  --surface-danger-border: #f5c2c7;
  --surface-success: #277c43;
  --surface-success-soft: #f3fcf6;
  --surface-success-border: #badbcc;
  --surface-warning: #be501e;
  --surface-warning-soft: #fff9eb;
  --surface-warning-border: #ffecb5;
  --surface-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --surface-mono: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
}
:root[data-theme="light"] {
  color-scheme: light;
  --surface-canvas: #f7f7f7;
  --surface-card: #ffffff;
  --surface-subtle: #f0f2f4;
  --surface-hover: #e9ecef;
  --surface-border: #e1e4e8;
  --surface-border-strong: #d0d5dd;
  --surface-text: #161616;
  --surface-muted: #5f6368;
  --surface-primary: #2272b4;
  --surface-primary-hover: #0e538b;
  --surface-primary-soft: rgba(34, 114, 180, 0.08);
  --surface-primary-text: #ffffff;
  --surface-danger: #c82d4c;
  --surface-danger-soft: #fff5f7;
  --surface-danger-border: #f5c2c7;
  --surface-success: #277c43;
  --surface-success-soft: #f3fcf6;
  --surface-success-border: #badbcc;
  --surface-warning: #be501e;
  --surface-warning-soft: #fff9eb;
  --surface-warning-border: #ffecb5;
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-canvas: #0f1418;
  --surface-card: #182026;
  --surface-subtle: #1f272e;
  --surface-hover: #26313a;
  --surface-border: #28333d;
  --surface-border-strong: #384654;
  --surface-text: #e8ecf0;
  --surface-muted: #95a3af;
  --surface-primary: #4299e0;
  --surface-primary-hover: #69b4ee;
  --surface-primary-soft: rgba(66, 153, 224, 0.12);
  --surface-primary-text: #0f1418;
  --surface-danger: #ff6b86;
  --surface-danger-soft: rgba(255, 107, 134, 0.12);
  --surface-danger-border: rgba(255, 107, 134, 0.28);
  --surface-success: #70c98f;
  --surface-success-soft: rgba(112, 201, 143, 0.12);
  --surface-success-border: rgba(112, 201, 143, 0.28);
  --surface-warning: #e7a65a;
  --surface-warning-soft: rgba(231, 166, 90, 0.12);
  --surface-warning-border: rgba(231, 166, 90, 0.28);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-canvas: #0f1418;
    --surface-card: #182026;
    --surface-subtle: #1f272e;
    --surface-hover: #26313a;
    --surface-border: #28333d;
    --surface-border-strong: #384654;
    --surface-text: #e8ecf0;
    --surface-muted: #95a3af;
    --surface-primary: #4299e0;
    --surface-primary-hover: #69b4ee;
    --surface-primary-soft: rgba(66, 153, 224, 0.12);
    --surface-primary-text: #0f1418;
    --surface-danger: #ff6b86;
    --surface-danger-soft: rgba(255, 107, 134, 0.12);
    --surface-danger-border: rgba(255, 107, 134, 0.28);
    --surface-success: #70c98f;
    --surface-success-soft: rgba(112, 201, 143, 0.12);
    --surface-success-border: rgba(112, 201, 143, 0.28);
    --surface-warning: #e7a65a;
    --surface-warning-soft: rgba(231, 166, 90, 0.12);
    --surface-warning-border: rgba(231, 166, 90, 0.28);
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--surface-font);
  font-size: 13px;
  line-height: 18px;
  background-color: var(--surface-canvas);
  color: var(--surface-text);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.shell-header {
  height: 48px;
  background: var(--surface-card);
  border-bottom: 1px solid var(--surface-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.shell-brand { display: flex; align-items: center; gap: 12px; }
.shell-brand h1 { font-size: 15px; font-weight: 700; letter-spacing: -0.2px; }
.surface-badge {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  background: var(--surface-subtle);
  border: 1px solid var(--surface-border);
  border-radius: 999px;
  color: var(--surface-muted);
}
.shell-header-right { display: flex; align-items: center; gap: 10px; }
.theme-control { display: inline-flex; align-items: center; margin: 0; padding: 0; }
.theme-toggle-group {
  display: inline-flex;
  align-items: center;
  background: var(--surface-subtle);
  border: 1px solid var(--surface-border);
  border-radius: 999px;
  padding: 2px;
  gap: 2px;
}
.theme-toggle-btn {
  background: transparent;
  border: none;
  border-radius: 999px;
  color: var(--surface-muted);
  cursor: pointer;
  font-family: inherit;
  font-size: 11px;
  font-weight: 500;
  line-height: 14px;
  padding: 3px 9px;
  transition: background 120ms ease, color 120ms ease;
}
.theme-toggle-btn:hover {
  color: var(--surface-text);
}
.theme-toggle-btn.active {
  background: var(--surface-card);
  color: var(--surface-text);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
:root[data-theme="dark"] .theme-toggle-btn.active {
  background: var(--surface-hover);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.32);
}
.theme-toggle-btn:focus-visible {
  outline: 2px solid var(--surface-primary);
  outline-offset: 1px;
}
.shell-status { display: flex; align-items: center; gap: 8px; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid transparent;
}
.pill-starting { background: var(--surface-primary-soft); color: var(--surface-primary); border-color: var(--surface-primary); }
.pill-ready { background: var(--surface-success-soft); color: var(--surface-success); border-color: var(--surface-success-border); }
.pill-failed, .pill-degraded, .pill-shutdown-failed { background: var(--surface-danger-soft); color: var(--surface-danger); border-color: var(--surface-danger-border); }
.pill-stopped, .pill-bootstrap { background: var(--surface-subtle); color: var(--surface-muted); border-color: var(--surface-border-strong); }
.pulse-dot { width: 7px; height: 7px; border-radius: 50%; background-color: currentColor; opacity: 0.85; }
.shell-main {
  flex: 1;
  max-width: 980px;
  width: 100%;
  margin: 0 auto;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.intro-panel { display: flex; flex-direction: column; gap: 4px; }
.intro-panel h2 { font-size: 18px; font-weight: 600; }
.intro-panel p { color: var(--surface-muted); }
.card {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--surface-border);
}
.card-title { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.data-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px 20px;
  margin-bottom: 12px;
}
.data-item dt {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--surface-muted);
  margin-bottom: 2px;
}
.data-item dd { font-size: 13px; font-weight: 500; word-break: break-word; }
.data-item dd code { font-family: var(--surface-mono); font-size: 12px; }
.banner {
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 17px;
  margin-bottom: 16px;
  border: 1px solid transparent;
}
.banner-info { background: var(--surface-primary-soft); color: var(--surface-primary); border-color: var(--surface-border); }
.banner-danger { background: var(--surface-danger-soft); color: var(--surface-danger); border-color: var(--surface-danger-border); }
.banner-warning { background: var(--surface-warning-soft); color: var(--surface-warning); border-color: var(--surface-warning-border); }
.stepper-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px; }
.stepper-table th {
  text-align: left;
  padding: 8px 12px;
  font-weight: 600;
  color: var(--surface-muted);
  border-bottom: 1px solid var(--surface-border);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.stepper-table td { padding: 9px 12px; border-bottom: 1px solid var(--surface-border); }
.stepper-table tr:last-child td { border-bottom: none; }
.step-num { width: 32px; color: var(--surface-muted); font-weight: 500; }
.step-name { font-weight: 500; }
.step-target { color: var(--surface-muted); font-family: var(--surface-mono); font-size: 11px; }
.step-status { text-align: right; width: 140px; }
.step-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.step-done { background: var(--surface-success-soft); color: var(--surface-success); }
.step-active { background: var(--surface-primary-soft); color: var(--surface-primary); }
.step-pending { background: var(--surface-subtle); color: var(--surface-muted); }
.step-failed { background: var(--surface-danger-soft); color: var(--surface-danger); }
.button-row { display: flex; align-items: center; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 4px;
  border: 1px solid transparent;
  cursor: pointer;
  text-decoration: none;
  font-family: inherit;
}
.btn:focus-visible { outline: 2px solid var(--surface-primary); outline-offset: 2px; }
.btn-primary { background: var(--surface-primary); color: var(--surface-primary-text); }
.btn-primary:hover:not(:disabled) { background: var(--surface-primary-hover); }
.btn-secondary { background: var(--surface-card); color: var(--surface-text); border-color: var(--surface-border-strong); }
.btn-secondary:hover:not(:disabled) { background: var(--surface-hover); }
.btn:disabled { opacity: 0.55; cursor: not-allowed; }
.create-form { margin-top: 14px; display: flex; flex-direction: column; gap: 12px; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-size: 12px; font-weight: 600; }
.form-field input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--surface-border-strong);
  border-radius: 4px;
  background: var(--surface-card);
  color: var(--surface-text);
  font-family: inherit;
  font-size: 13px;
  max-width: 480px;
  width: 100%;
}
.form-field input:focus { outline: 2px solid var(--surface-primary); border-color: transparent; }
.form-help { font-size: 12px; color: var(--surface-muted); }
details.diagnostics-box {
  margin-top: 14px;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: var(--surface-subtle);
  overflow: hidden;
}
details.diagnostics-box summary { padding: 8px 12px; font-size: 12px; font-weight: 600; cursor: pointer; user-select: none; }
details.diagnostics-box summary:focus-visible { outline: 2px solid var(--surface-primary); }
.diagnostics-content { padding: 12px; border-top: 1px solid var(--surface-border); background: var(--surface-card); }
#diagnostics { font-family: var(--surface-mono); font-size: 11px; line-height: 16px; white-space: pre-wrap; word-break: break-all; }
#service { font-weight: 600; color: var(--surface-danger); margin-bottom: 6px; font-size: 12px; }
.startup-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: var(--surface-canvas);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px 24px;
  overflow: auto;
}
.overlay-panel {
  width: 100%;
  max-width: 720px;
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.overlay-head { display: flex; align-items: center; gap: 12px; }
.overlay-head h2 { font-size: 16px; font-weight: 600; }
.overlay-spinner {
  flex: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid var(--surface-primary-soft);
  border-top-color: var(--surface-primary);
  animation: overlay-spin 0.9s linear infinite;
}
.overlay-status { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--surface-muted); }
.startup-overlay .pulse-dot { animation: overlay-pulse 1.6s ease-in-out infinite; }
.overlay-panel .stepper-table { margin-top: 0; }
@keyframes overlay-spin { to { transform: rotate(360deg); } }
@keyframes overlay-pulse { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
  .overlay-spinner { animation: none; }
  .startup-overlay .pulse-dot { animation: none; }
}
.shell-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--surface-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: var(--surface-muted);
  background: var(--surface-card);
}
@media (max-width: 720px) {
  .shell-main { padding: 16px 12px; }
  .step-target { display: none; }
}"#;

/// Render the workspace-management surface: the single app-owned top-level
/// surface that presents the local workspace record, the real initialization
/// steps, the runtime controls, and the finite failure record in the SAME main
/// window. It replaces the former separate first-run form and runtime-control
/// page: creation is an inline action of this surface, and the other top-level
/// surface is the existing workspace SPA this window navigates to on readiness.
///
/// Controls are plain form submissions to the bundled surface (no script, no
/// Tauri command, no capability): Start/Retry maps to the existing `start`
/// operation with a single bounded attempt, Stop/Cancel maps to the existing
/// `stop` operation, and Open navigates this window to the owned loopback SPA.
/// Each is disabled where the action cannot apply, so the surface never offers
/// an empty success path.
///
/// Content is sanitized by construction: state word, finite failure code,
/// failing service name, the validated workspace name/id, the owned PID, and at
/// most the occupied-port observation. No secret, key, credential, raw service
/// output, log line, or filesystem path is ever rendered, and no step is ever
/// invented: a step is only `Done` when this process observed the real signal.
#[must_use]
pub fn render_workspace_management(view: &ManagementView) -> String {
    let state = view.state.as_str();
    let total = view.steps.len();
    let done = view
        .steps
        .iter()
        .filter(|step| step.status == StepStatus::Done)
        .count();
    let summary = format!("{done} of {total} steps done");
    let (banner_class, banner_message) = state_notice(view);
    let service_line = match view.failure.as_ref().and_then(|record| record.service.clone()) {
        Some(service) => format!("Failing service: {service}"),
        None => "Failing service: not reported by the runtime".to_string(),
    };
    let diagnostics = diagnostics_text(view);
    let details_open = if view.refusal.is_some()
        || matches!(
            view.state,
            LifecycleState::Failed | LifecycleState::Degraded | LifecycleState::ShutdownFailed
        )
    {
        "open"
    } else {
        ""
    };
    let refresh = if view.is_live() {
        format!("<meta http-equiv=\"refresh\" content=\"2; url={BOOTSTRAP_SURFACE_URL}\">")
    } else {
        String::new()
    };
    let rows = steps_rows_html(&view.steps);
    // The startup overlay is a distinct layer above the shell while an action
    // the user started is in flight. While it is shown the shell below is
    // `inert`, so focus cannot land on controls the overlay covers; the
    // overlay itself is a plain non-modal layer (no script, no focus
    // management), the window's normal close always works, and the shell
    // becomes fully reachable again the moment the overlay disappears.
    let overlay = overlay_html(view);
    let main_inert = if overlay.is_empty() { "" } else { " inert" };
    let start_disabled = if view.can_start { "" } else { "disabled" };
    let stop_disabled = if view.can_stop() { "" } else { "disabled" };
    let open_disabled = if view.state == LifecycleState::Ready {
        ""
    } else {
        "disabled"
    };
    let start_label = match view.state {
        LifecycleState::Failed | LifecycleState::Degraded => "Retry startup",
        _ => "Start runtime",
    };
    let stop_label = if view.state == LifecycleState::Starting {
        "Cancel startup"
    } else {
        "Stop runtime"
    };
    let workspace_section = workspace_section_html(view);
    let theme_mode = view.theme_mode;
    let theme_attr = match theme_mode {
        ThemeMode::Light => " data-theme=\"light\"",
        ThemeMode::Dark => " data-theme=\"dark\"",
        ThemeMode::System => " data-theme=\"system\"",
    };
    let light_active = if theme_mode == ThemeMode::Light { " active" } else { "" };
    let dark_active = if theme_mode == ThemeMode::Dark { " active" } else { "" };
    let system_active = if theme_mode == ThemeMode::System { " active" } else { "" };
    let light_pressed = if theme_mode == ThemeMode::Light { "true" } else { "false" };
    let dark_pressed = if theme_mode == ThemeMode::Dark { "true" } else { "false" };
    let system_pressed = if theme_mode == ThemeMode::System { "true" } else { "false" };
    format!(
        r#"<!doctype html>
<html lang="en"{theme_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{refresh}
<title>Projecta</title>
<style>
{SURFACE_STYLE}
</style>
</head>
<body>
{overlay}
<header class="shell-header">
<div class="shell-brand">
<h1>Projecta</h1>
<span class="surface-badge">Workspace management</span>
</div>
<div class="shell-header-right">
<form method="get" action="{BOOTSTRAP_SURFACE_URL}runtime" class="theme-control" data-testid="lifecycle-theme-form">
<input type="hidden" name="intent" value="theme">
<div class="theme-toggle-group" role="radiogroup" aria-label="Appearance">
<button type="submit" name="mode" value="light" class="theme-toggle-btn{light_active}" aria-pressed="{light_pressed}" title="Light theme">Light</button>
<button type="submit" name="mode" value="dark" class="theme-toggle-btn{dark_active}" aria-pressed="{dark_pressed}" title="Dark theme">Dark</button>
<button type="submit" name="mode" value="system" class="theme-toggle-btn{system_active}" aria-pressed="{system_pressed}" title="Follow system theme">System</button>
</div>
</form>
<div class="shell-status">
<span class="pill pill-{state}">
<span class="pulse-dot"></span>
<span id="state" data-testid="lifecycle-state">{state}</span>
</span>
</div>
</div>
</header>
<main class="shell-main"{main_inert}>
<div class="intro-panel">
<h2>Local workspace and runtime</h2>
<p>This window owns one local workspace on this computer and starts only its own services.</p>
</div>
{workspace_section}
<section class="card" aria-labelledby="runtime-card-title">
<div class="card-header">
<h3 class="card-title" id="runtime-card-title">Runtime service initialization</h3>
<span class="surface-badge" data-testid="init-summary">{summary}</span>
</div>
<div class="banner {banner_class}">{banner_message}</div>
<table class="stepper-table" aria-label="Runtime service initialization steps">
<thead>
<tr><th class="step-num">#</th><th>Service step</th><th>Target / port</th><th class="step-status">Status</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
<details class="diagnostics-box" {details_open}>
<summary>Diagnostics</summary>
<div class="diagnostics-content">
<p id="service" data-testid="lifecycle-failing-service">{service_line}</p>
<pre id="diagnostics" data-testid="lifecycle-diagnostics">{diagnostics}</pre>
</div>
</details>
<form method="get" action="{BOOTSTRAP_SURFACE_URL}runtime" data-testid="lifecycle-runtime-form">
<div class="button-row">
<button id="start" class="btn btn-primary" type="submit" name="intent" value="start" data-testid="lifecycle-start" {start_disabled}>{start_label}</button>
<button id="stop" class="btn btn-secondary" type="submit" name="intent" value="stop" data-testid="lifecycle-stop" {stop_disabled}>{stop_label}</button>
<button id="open" class="btn btn-secondary" type="submit" name="intent" value="open" data-testid="lifecycle-open" {open_disabled}>Open project workspace</button>
</div>
</form>
</section>
</main>
<footer class="shell-footer">
<span>Closing this window cancels startup and stops only the services Projecta started.</span>
<span>Local machine only</span>
</footer>
</body>
</html>"#,
    )
}

/// The eight step rows shared by the management surface's table and the
/// startup overlay, so both read the same real observation model and no step
/// can be shown as done without its own observation.
fn steps_rows_html(steps: &[InitStep]) -> String {
    steps
        .iter()
        .enumerate()
        .map(|(index, step)| {
            let (class, label) = step.status.badge();
            format!(
                "<tr><td class=\"step-num\">{number}</td><td class=\"step-name\">{name}</td><td class=\"step-target\">{target}</td><td class=\"step-status\"><span class=\"step-badge {class}\" data-testid=\"init-step-{key}\">{label}</span></td></tr>",
                number = index + 1,
                name = step.label,
                target = step.target,
                class = class,
                key = step.key,
                label = label,
            )
        })
        .collect()
}

/// The startup overlay: a distinct layer above the workspace-management shell
/// that is rendered only while this app is objectively in the real `starting`
/// window — creating the workspace record on an unprovisioned root, or
/// starting the owned runtime services. It shows the same real observations as
/// the shell (no timer, no percentage, no invented step), keeps the cancel
/// binding of the existing `stop` operation reachable while it covers the
/// shell, and is dismissed as soon as readiness or a terminal outcome makes
/// the management surface the truthful view again. It is a plain layer of the
/// same server-rendered document: no script, no dialog semantics, no focus
/// management — the ordinary window close and every keyboard binding keep
/// working.
fn overlay_html(view: &ManagementView) -> String {
    let Some(mode) = view.overlay() else {
        return String::new();
    };
    let total = view.steps.len();
    let done = view
        .steps
        .iter()
        .filter(|step| step.status == StepStatus::Done)
        .count();
    match mode {
        OverlayMode::Creating => r#"<div class="startup-overlay" data-testid="startup-overlay" data-overlay-mode="creating">
<div class="overlay-panel">
<div class="overlay-head">
<span class="overlay-spinner" aria-hidden="true"></span>
<h2>Creating your local workspace</h2>
</div>
<p class="overlay-status"><span class="pulse-dot" aria-hidden="true"></span>Writing this computer's workspace record; the real outcome is reported here.</p>
<p class="form-help">One bounded attempt (up to about two minutes) &mdash; nothing is uploaded and nothing outside this computer is written. No service starts before the workspace exists. Closing this window cancels the creation: the data root is left with a complete record or none, never a partial one.</p>
</div>
</div>"#
            .to_string(),
        OverlayMode::Starting => format!(
            r#"<div class="startup-overlay" data-testid="startup-overlay" data-overlay-mode="starting">
<div class="overlay-panel">
<div class="overlay-head">
<span class="overlay-spinner" aria-hidden="true"></span>
<h2>Starting the local runtime</h2>
</div>
<p class="overlay-status"><span class="pulse-dot" aria-hidden="true"></span>{done} of {total} steps done &middot; this page refreshes every 2 seconds from real service state</p>
<table class="stepper-table" aria-label="Runtime service initialization steps">
<thead>
<tr><th class="step-num">#</th><th>Service step</th><th>Target / port</th><th class="step-status">Status</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
<form method="get" action="{BOOTSTRAP_SURFACE_URL}runtime" data-testid="overlay-runtime-form">
<div class="button-row">
<button class="btn btn-secondary" type="submit" name="intent" value="stop" data-testid="overlay-stop">Cancel startup</button>
</div>
</form>
<p class="form-help">Cancel startup stops only the services Projecta started and keeps your data; closing this window also cancels startup. If a step fails, this overlay closes and the management surface shows the failure code, the failing service, and the diagnostics.</p>
</div>
</div>"#,
            done = done,
            total = total,
            rows = steps_rows_html(&view.steps),
        ),
    }
}

/// Workspace card of the management surface: the provisioned record, the
/// inline create action on an unprovisioned data root, or a finite statement
/// when the record cannot be read. The root path itself is never rendered.
fn workspace_section_html(view: &ManagementView) -> String {
    match &view.workspace {
        WorkspaceRecord::Active { name, project_id } => format!(
            r#"<section class="card" aria-labelledby="workspace-info-title">
<div class="card-header">
<h3 class="card-title" id="workspace-info-title">Local workspace</h3>
<span class="surface-badge">Provisioned</span>
</div>
<dl class="data-grid">
<div class="data-item"><dt>Workspace name</dt><dd data-testid="workspace-name"><strong>{name}</strong></dd></div>
<div class="data-item"><dt>Workspace ID</dt><dd><code data-testid="workspace-id">{project_id}</code></dd></div>
<div class="data-item"><dt>Projects</dt><dd>Listed by the workspace itself once it is ready</dd></div>
<div class="data-item"><dt>Privacy</dt><dd>This computer only</dd></div>
</dl>
<p class="form-help">When every step below is done, this window opens the project workspace automatically.</p>
</section>"#,
            name = escape_html(name),
            project_id = escape_html(project_id),
        ),
        WorkspaceRecord::Absent if view.first_run => {
            // The create controls are locked for exactly the real in-flight
            // state the overlay reports: an accepted creation request whose
            // owned child is still writing the workspace record.
            let provisioning = view.provision_pending && view.state == LifecycleState::Starting;
            let refusal = view
                .refusal
                .as_deref()
                .filter(|code| is_finite_code(code))
                .map(|code| {
                    // The name rule keeps its exact guidance; every other
                    // finite refusal (an accepted create already in flight, an
                    // existing record, no bundled package, a failed or
                    // timed-out child) is stated as itself instead of being
                    // re-labelled a name problem.
                    let message = if code == "WORKSPACE_NAME_INVALID" {
                        "That name is not accepted [WORKSPACE_NAME_INVALID]. Enter a non-empty name of at most 128 characters that produces a valid local project ID.".to_string()
                    } else {
                        format!(
                            "The create request was refused [{code}]. Nothing was written by this submission, and the window never retries by itself."
                        )
                    };
                    format!(
                        "<div class=\"banner banner-danger\" id=\"refusal\" data-testid=\"first-run-refusal\">{message}</div>"
                    )
                })
                .unwrap_or_default();
            let progress = if provisioning {
                "<div class=\"banner banner-info\" data-testid=\"first-run-progress\">Creating your local workspace on this computer; this window reports the real outcome and never retries by itself.</div>"
            } else {
                ""
            };
            let input_disabled = if provisioning { "disabled" } else { "" };
            let create_label = if provisioning {
                "Creating workspace…"
            } else {
                "Create workspace and start"
            };
            format!(
                r#"<section class="card" aria-labelledby="workspace-create-title">
<div class="card-header">
<h3 class="card-title" id="workspace-create-title">Create the local workspace</h3>
<span class="surface-badge">No workspace yet</span>
</div>
<p class="form-help">This computer only: nothing is uploaded, and a name that cannot produce a valid local project ID is refused without writing partial state.</p>
{progress}
{refusal}
<form method="get" action="http://{BOOTSTRAP_WORKAROUND_HOST}/provision" data-testid="first-run-form" class="create-form">
<div class="form-field">
<label for="workspace-name">Workspace display name</label>
<input id="workspace-name" name="name" type="text" maxlength="128" placeholder="{placeholder}" data-testid="first-run-name" required {input_disabled}>
<span class="form-help">1 to 128 characters. The local workspace keeps its own projects and data.</span>
</div>
<div class="button-row">
<button class="btn btn-primary" type="submit" name="intent" value="create" data-testid="first-run-create" {input_disabled}>{create_label}</button>
<button class="btn btn-secondary" type="submit" name="intent" value="cancel" data-testid="first-run-cancel" {input_disabled}>Cancel</button>
</div>
</form>
</section>"#,
                progress = progress,
                refusal = refusal,
                placeholder = escape_html(view_default_name()),
                input_disabled = input_disabled,
                create_label = create_label,
            )
        }
        WorkspaceRecord::Absent => r#"<section class="card" aria-labelledby="workspace-missing-title">
<div class="card-header">
<h3 class="card-title" id="workspace-missing-title">Local workspace</h3>
<span class="surface-badge">Record missing</span>
</div>
<div class="banner banner-warning">The workspace record is not on disk while this app is already running, so nothing is created automatically. Close Projecta and open it again to create a workspace on this data root.</div>
</section>"#
            .to_string(),
        WorkspaceRecord::Unreadable => r#"<section class="card" aria-labelledby="workspace-invalid-title">
<div class="card-header">
<h3 class="card-title" id="workspace-invalid-title">Local workspace</h3>
<span class="surface-badge">Unreadable record</span>
</div>
<div class="banner banner-danger">The local workspace record is present but not valid [LOCAL_PROJECT_CONFIGURATION_INVALID]. Nothing was overwritten or recreated. The runtime, if started, reports its own finite failure; creating a workspace over an unreadable record is refused.</div>
</section>"#
            .to_string(),
    }
}

/// Default display name offered as the create-card placeholder. Mirrors the
/// launcher's own `FIRST_RUN_DISPLAY_NAME`; the authoritative default stays in
/// the Python launcher.
#[must_use]
fn view_default_name() -> &'static str {
    "My Projecta Workspace"
}

/// The state notice (banner class + message) for the current view. Every branch
/// restates the observed state and the bounded user action; no branch promises
/// a retry, a repair, or a success that did not happen.
#[must_use]
fn state_notice(view: &ManagementView) -> (&'static str, String) {
    let origin = view.api_origin.trim_end_matches('/');
    let code = view
        .failure
        .as_ref()
        .map(|record| record.code.as_str())
        .unwrap_or_default();
    let service = view
        .failure
        .as_ref()
        .and_then(|record| record.service.clone());
    if view.stop_pending {
        return (
            "banner-warning",
            "Stop requested; stopping only the services Projecta started. Your data is kept.".to_string(),
        );
    }
    if view.start_pending && view.state != LifecycleState::Starting {
        return (
            "banner-info",
            "Start requested; starting the owned services for this workspace. The runtime starts once and reports its real outcome.".to_string(),
        );
    }
    match view.state {
        LifecycleState::Bootstrap if view.first_run => (
            "banner-info",
            "No local workspace exists on this data root yet. Create one below; no service is started before that.".to_string(),
        ),
        LifecycleState::Bootstrap => (
            "banner-info",
            "Runtime bootstrap: no service is started yet. The owned runtime starts once for this workspace; use Retry startup only after a failure.".to_string(),
        ),
        LifecycleState::Starting => (
            "banner-info",
            format!(
                "Starting the owned services for this workspace; waiting for {origin}/health/ready. Cancel startup stops only those services and keeps your data."
            ),
        ),
        LifecycleState::Ready => (
            "banner-info",
            format!(
                "Backend ready at {origin}. This window opens the project workspace automatically; Stop runtime stops only the owned services, or close the window to stop them and quit."
            ),
        ),
        LifecycleState::Stopped => (
            "banner-info",
            "The runtime is stopped. Locks and ports are released and your data was retained. Start runtime runs it again for this workspace.".to_string(),
        ),
        LifecycleState::Failed if view.first_run => (
            "banner-danger",
            format!(
                "Creating the local workspace did not complete [{code}]. A stopped creation leaves a complete record or none \u{2014} never a partial one \u{2014} and nothing is retried automatically. Review the diagnostics, then submit the create form again for one new bounded attempt, or close the window."
            ),
        ),
        LifecycleState::Failed => (
            "banner-danger",
            format!(
                "Startup failed [{code}].{}{} No second service tree was started and your data was retained. Resolve the cause, then Retry startup for one bounded attempt, or close the window.",
                service
                    .as_ref()
                    .map(|service| format!(" Failing service: {service}."))
                    .unwrap_or_default(),
                view.failure
                    .as_ref()
                    .and_then(|record| record.detail.clone())
                    .map(|detail| format!(" Occupied dependency: {detail}."))
                    .unwrap_or_default(),
            ),
        ),
        LifecycleState::Degraded => (
            "banner-warning",
            format!(
                "The runtime stopped after it was ready [{code}].{} Only the owned services were stopped and your data was retained. Retry startup makes a single bounded recovery attempt.",
                service
                    .as_ref()
                    .map(|service| format!(" Service '{service}' stopped reporting readiness."))
                    .unwrap_or_default(),
            ),
        ),
        LifecycleState::ShutdownFailed => (
            "banner-danger",
            format!(
                "Graceful stop did not complete [{code}]. The owned manager is waiting for an explicit stop retry; nothing outside the owned tree was touched and your data was retained. Use Stop runtime to retry, or close the window."
            ),
        ),
    }
}

/// Full diagnostics text for the details box: the same finite facts the banner
/// states, plus the observed state, code, failing service, and occupied-port
/// observation. Rendered inside `<pre>`; every line is either a finite token, a
/// fixed sentence, or an already sanitized value.
#[must_use]
fn diagnostics_text(view: &ManagementView) -> String {
    let mut lines = vec![
        format!("State: {}", view.state.as_str()),
        match view.supervisor_pid {
            Some(pid) => format!("Owned supervisor process: {pid}"),
            None => "Owned supervisor process: none".to_string(),
        },
    ];
    match view.failure.as_ref() {
        Some(record) => {
            lines.push(format!("Failure code: {}", record.code));
            if let Some(service) = record.service.as_deref() {
                lines.push(format!("Failing service: {service}"));
            }
            if let Some(detail) = record.detail.as_deref() {
                lines.push(format!("Occupied dependency: {detail}"));
            }
        }
        None => lines.push("Failure code: none".to_string()),
    }
    let observed = view
        .steps
        .iter()
        .filter(|step| step.status == StepStatus::Done)
        .map(|step| step.label)
        .collect::<Vec<_>>();
    if !observed.is_empty() {
        lines.push(format!("Observed done: {}", observed.join(", ")));
    }
    if let Some(refusal) = view
        .refusal
        .as_deref()
        .filter(|code| is_finite_code(code))
    {
        lines.push(format!("Workspace creation refused: {refusal}"));
    }
    lines.push(state_notice(view).1);
    lines.join("\n")
}

/// Escape a value for a text node or a double-quoted HTML attribute.
///
/// The create card is the one place a user-supplied string re-enters HTML, so
/// it is escaped with the full five-character set (`& < > " '`) even though
/// every rendered value is already validated to be finite.
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

/// App-owned lifecycle controller: spawn/stop exactly one supervisor child,
/// poll readiness for the same-window management surface, and observe the real
/// initialization steps (package, supervisor child, fixed service ports, API
/// readiness). The blocking `cold_start` runs on a worker thread while
/// window-close handling signals cancellation from the event loop, and user
/// Start/Stop from the lifecycle surface drive the same bounded,
/// single-attempt operations.
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
    /// The owned `provision` child while a workspace creation is in flight, so
    /// ordinary close can cancel it (kill + reap) instead of leaving a
    /// half-writing process behind. Only this app's own child is ever touched.
    provision_child: Mutex<Option<Child>>,
    /// Whether an accepted workspace-creation request is still in flight — set
    /// synchronously by `begin_provision` before its worker runs and cleared
    /// when that worker returns, so the surface renders the creating overlay
    /// from the first render of the action rather than racing the child.
    provision_pending: AtomicBool,
    /// The provision worker remains active until it either reports a refusal
    /// or hands successful creation off to the runtime-start worker. This closes
    /// the spawn-then-publish handle race during Stop and window close.
    provision_worker_active: AtomicBool,
    provision_handle: Mutex<Option<JoinHandle<()>>>,
    /// Whether the data root had no workspace when this app launched. Read once
    /// in `new` (before provisioning), then cleared only by a successful
    /// `provision_first_run`, so a window that has just created its workspace
    /// does not re-decide it is still first-run and re-show the create card.
    first_run: AtomicBool,
    /// User-selected or system color scheme mode.
    theme_mode: Mutex<ThemeMode>,
}

impl LifecycleController {
    #[must_use]
    pub fn new(paths: Option<LifecyclePaths>, api_port: u16) -> Self {
        // First-run is decided once, before anything is provisioned.
        let first_run = matches!(&paths, Some(paths) if !paths.has_workspace());
        let initial_theme = paths
            .as_ref()
            .map(|p| p.read_ui_preferences().theme_mode)
            .unwrap_or_default();
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
            provision_child: Mutex::new(None),
            provision_pending: AtomicBool::new(false),
            provision_worker_active: AtomicBool::new(false),
            provision_handle: Mutex::new(None),
            first_run: AtomicBool::new(first_run),
            theme_mode: Mutex::new(initial_theme),
        }
    }

    /// Whether the launched data root has no workspace yet, so the window must
    /// show the inline create card instead of starting the owned tree.
    #[must_use]
    pub fn is_first_run(&self) -> bool {
        self.first_run.load(Ordering::SeqCst)
    }

    #[must_use]
    pub fn state(&self) -> LifecycleState {
        *self.state.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Current UI theme mode preference.
    #[must_use]
    pub fn theme_mode(&self) -> ThemeMode {
        *self.theme_mode.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Update UI theme mode preference in memory and persist to data root.
    pub fn set_theme_mode(&self, mode: ThemeMode) -> Result<(), String> {
        *self.theme_mode.lock().unwrap_or_else(|e| e.into_inner()) = mode;
        if let Some(paths) = &self.paths {
            let mut prefs = paths.read_ui_preferences();
            prefs.theme_mode = mode;
            paths.write_ui_preferences(&prefs).map_err(|e| e.to_string())?;
        }
        Ok(())
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
            .is_some_and(|supervisor| {
                supervisor.runtime_identity().is_some() && supervisor.is_running()
            })
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

    /// Build the workspace-management view from real observations of this
    /// app's own state: the validated workspace record, the owned supervisor
    /// handle, each fixed loopback port, and the API's own `/health/ready`
    /// document. Nothing is invented, nothing is sampled on a timer, and no
    /// foreign process or port is claimed as owned.
    ///
    /// The probes are skipped once the tree is objectively ready (all eight
    /// steps are done by definition) and in terminal states that cannot change
    /// on their own; a `Ready` view therefore costs nothing.
    #[must_use]
    pub fn management_view(&self) -> ManagementView {
        let state = self.state();
        let failure = self.failure();
        let supervisor_pid = self.supervisor_pid();
        let supervisor_alive = self.owned_supervisor_alive();
        let stop_pending = self.is_stop_pending();
        let start_pending = self.is_start_pending();
        let workspace = self
            .paths
            .as_ref()
            .map(LifecyclePaths::read_workspace_record)
            .unwrap_or(WorkspaceRecord::Absent);
        let observing = state != LifecycleState::Ready;
        let port_of = |name: &str| {
            FIXED_SERVICE_PORTS
                .iter()
                .find(|(service, _)| *service == name)
                .map(|(_, port)| *port)
        };
        let listening = |name: &str| {
            observing
                && supervisor_alive
                && port_of(name).is_some_and(|port| service_listening(port, LISTEN_PROBE_TIMEOUT))
        };
        let observations = InitObservations {
            package_resolved: self.paths.is_some(),
            supervisor_alive,
            postgres_listening: listening("postgres"),
            fuseki_listening: listening("fuseki"),
            semantic_listening: listening("semanticCore"),
            api_listening: observing
                && supervisor_alive
                && service_listening(self.api_port, LISTEN_PROBE_TIMEOUT),
            api_readiness: if observing && supervisor_alive {
                probe_api_readiness(self.api_port, LISTEN_PROBE_TIMEOUT)
            } else {
                ApiReadiness::default()
            },
        };
        let steps = build_init_steps(state, failure.as_ref(), &observations);
        ManagementView {
            state,
            workspace,
            steps,
            failure,
            api_origin: format!("http://{LOOPBACK_HOST}:{}/", self.api_port),
            supervisor_pid,
            start_pending,
            stop_pending,
            provision_pending: self.provision_in_flight(),
            can_start: self.can_start(),
            first_run: self.is_first_run(),
            refusal: None,
            theme_mode: self.theme_mode(),
        }
    }

    /// Stash the worker-thread handle running `cold_start` (setup path).
    pub fn set_startup_handle(&self, handle: JoinHandle<bool>) {
        let mut slot = self.startup_handle.lock().unwrap_or_else(|e| e.into_inner());
        if self.start_pending.load(Ordering::SeqCst) {
            *slot = Some(handle);
        } else {
            drop(slot);
            let _ = handle.join();
        }
    }

    /// Run `cold_start` on a worker thread and keep its handle so the close path
    /// can join it exactly once. A worker cancelled before it starts returns
    /// without spawning a supervisor child.
    pub fn spawn_cold_start(self: &std::sync::Arc<Self>) {
        self.join_startup_worker();
        self.start_pending.store(true, Ordering::SeqCst);
        if self.cancel_requested() {
            self.set_state(LifecycleState::Stopped, None);
            self.start_pending.store(false, Ordering::SeqCst);
            return;
        }
        let worker = Arc::clone(self);
        let startup_thread = std::thread::spawn(move || {
            let outcome = worker.cold_start();
            worker.start_pending.store(false, Ordering::SeqCst);
            outcome
        });
        self.set_startup_handle(startup_thread);
    }

    /// Take the worker-thread handle.
    pub fn take_startup_handle(&self) -> Option<JoinHandle<bool>> {
        self.startup_handle
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .take()
    }

    /// Wait through the spawn-then-publish interval as well as joining the
    /// worker, so close cannot miss a child whose handle is not stored yet.
    pub fn join_startup_worker(&self) {
        loop {
            if let Some(handle) = self.take_startup_handle() {
                let _ = handle.join();
                return;
            }
            if !self.start_pending.load(Ordering::SeqCst) {
                return;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
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
        if self.cancel_requested() {
            self.set_state(LifecycleState::Stopped, None);
            return false;
        }
        let previous_runtime_id = paths
            .read_runtime_status()
            .and_then(|status| status.runtime_id);
        let child = match OwnedSupervisor::spawn(
            &paths.supervisor_exe,
            &paths.local_app_data,
            previous_runtime_id,
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
        let started = Instant::now();
        while started.elapsed() < STARTUP_DEADLINE {
            if self.cancel_requested() {
                self.cancel_start();
                return false;
            }
            let (alive, runtime_identity) = {
                let mut guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
                let Some(supervisor) = guard.as_mut() else {
                    return false;
                };
                let alive = supervisor.is_running();
                if alive {
                    supervisor.observe_runtime_identity(&paths);
                }
                (alive, supervisor.runtime_identity().cloned())
            };
            if !alive {
                let (code, service) = self.reap_supervisor_failure();
                self.set_failure(LifecycleState::Failed, code, service);
                return false;
            }
            if let Some(identity) = runtime_identity {
                let manager_ready = paths.read_runtime_status().is_some_and(|status| {
                    status.runtime_id.as_deref() == Some(identity.runtime_id.as_str())
                        && status.manager_pid == Some(identity.manager_pid)
                        && status.state.as_deref() == Some("ready")
                });
                if manager_ready
                    && poll_api_ready(self.api_port, Duration::from_secs(2)) == Readiness::Ready
                {
                    self.set_state(LifecycleState::Ready, None);
                    return true;
                }
            }
            std::thread::sleep(Duration::from_millis(500));
        }
        if self.cancel_requested() {
            self.cancel_start();
            return false;
        }
        let (still_running, owns_runtime) = {
            let mut guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
            let Some(supervisor) = guard.as_mut() else {
                return false;
            };
            let still_running = supervisor.is_running();
            if still_running {
                supervisor.observe_runtime_identity(&paths);
            }
            (still_running, supervisor.runtime_identity().is_some())
        };
        if !still_running {
            let (code, service) = self.reap_supervisor_failure();
            self.set_failure(LifecycleState::Failed, code, service);
        } else if owns_runtime {
            self.stop_owned(STOP_TIMEOUT);
            self.set_failure(
                LifecycleState::Failed,
                "SERVICE_READINESS_TIMEOUT".to_string(),
                None,
            );
        } else {
            // This child never proved that it acquired the shared runtime
            // lock. Terminate only this exact child/job; never send the shared
            // data root's stop request.
            self.stop_owned_prompt();
            self.set_failure(
                LifecycleState::Failed,
                "SUPERVISOR_IDENTITY_TIMEOUT".to_string(),
                None,
            );
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
        let (stderr_code, runtime_identity) = match self
            .supervisor
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .take()
        {
            Some(mut supervisor) => {
                let identity = supervisor.runtime_identity().cloned();
                let code = supervisor.reap_failure_code();
                ((code != "SUPERVISOR_EXITED").then_some(code), identity)
            }
            None => (None, None),
        };
        let status_failure = runtime_identity.and_then(|identity| {
            self.paths
                .as_ref()
                .and_then(LifecyclePaths::read_runtime_status)
                .filter(|status| {
                    status.runtime_id.as_deref() == Some(identity.runtime_id.as_str())
                        && status.manager_pid == Some(identity.manager_pid)
                })
                .and_then(|status| status.failure)
        });
        match (stderr_code, status_failure) {
            (Some(code), Some(record)) if record.code == code => (code, record.service),
            (Some(code), _) => (code, None),
            (None, Some(record)) => (record.code, record.service),
            (None, None) => ("SUPERVISOR_EXITED".to_string(), None),
        }
    }

    /// Validate a create request and the refusal conditions in this process, so
    /// a refusal returns as a refusal render and never spawns a writer or
    /// leaves partial state. Returns the trimmed display name.
    ///
    /// The checks mirror the launcher's own rules and the surface's contract:
    /// an owned supervisor already exists, no bundled package resolved, the
    /// root is no longer first-run (never reseed), a create is already in
    /// flight (never a second writer for the same data root), and the audited
    /// name rule.
    fn validate_create_request(&self, raw_name: &str) -> Result<String, String> {
        if self.has_supervisor() {
            return Err("ALREADY_STARTED".to_string());
        }
        if self.paths.is_none() {
            // No bundled package at all: fail closed with the finite code rather
            // than offering a create card that could never provision.
            self.set_failure(
                LifecycleState::Failed,
                "RUNTIME_PACKAGE_MISSING".to_string(),
                None,
            );
            return Err("RUNTIME_PACKAGE_MISSING".to_string());
        }
        if !self.first_run.load(Ordering::SeqCst) {
            // An existing workspace is present (or was just created): nothing
            // to provision. Never reseed, never overwrite.
            return Err("WORKSPACE_ALREADY_PROVISIONED".to_string());
        }
        if self.is_provisioning() {
            // A create is already in flight; a second submission must not spawn
            // a second writer for the same data root.
            return Err("PROVISION_IN_PROGRESS".to_string());
        }
        match validate_workspace_name(raw_name) {
            Ok(trimmed) => Ok(trimmed),
            // A refused name changes nothing: no state transition, no child
            // process, no file written.
            Err(code) => Err(code.to_string()),
        }
    }

    /// Surface entry of the inline create card: accept the request
    /// synchronously (with the same validation the blocking body applies, so a
    /// refused name still returns as a refusal render and spawns nothing), set
    /// the real `starting` state and the in-flight marker before returning,
    /// and run the owned `provision` child on a worker thread.
    ///
    /// The window therefore renders the creating overlay for the very action
    /// the user submitted and keeps refreshing to the real outcome; it is
    /// never held on a blocking request. On success the worker continues
    /// straight into the ordinary cold start, so first-run provisioning stays
    /// one continuous journey.
    pub fn begin_provision(self: &std::sync::Arc<Self>, raw_name: &str) -> Result<(), String> {
        if self.provision_in_flight() {
            return Err("PROVISION_IN_PROGRESS".to_string());
        }
        self.join_provision_worker();
        let trimmed = self.validate_create_request(raw_name)?;
        self.cancel.store(false, Ordering::SeqCst);
        self.set_state(LifecycleState::Starting, None);
        self.provision_pending.store(true, Ordering::SeqCst);
        self.provision_worker_active.store(true, Ordering::SeqCst);
        let worker = std::sync::Arc::clone(self);
        let handle = std::thread::spawn(move || {
            // Publish the handle before this worker may spawn a child. Close
            // and Stop can therefore always join the exact active worker.
            std::thread::park();
            let outcome = worker.provision_first_run(&trimmed);
            worker.provision_pending.store(false, Ordering::SeqCst);
            if outcome.is_ok() {
                worker.spawn_cold_start();
            }
            worker
                .provision_worker_active
                .store(false, Ordering::SeqCst);
        });
        self.set_provision_handle(handle);
        Ok(())
    }

    fn set_provision_handle(&self, handle: JoinHandle<()>) {
        let worker = handle.thread().clone();
        *self
            .provision_handle
            .lock()
            .unwrap_or_else(|e| e.into_inner()) = Some(handle);
        worker.unpark();
    }

    fn join_provision_worker(&self) {
        loop {
            if let Some(handle) = self
                .provision_handle
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .take()
            {
                let _ = handle.join();
                return;
            }
            if !self.provision_worker_active.load(Ordering::SeqCst) {
                return;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
    }

    /// Whether a workspace-creation request is accepted and still in flight:
    /// the synchronous marker set by `begin_provision` or its owned `provision`
    /// child. The surface renders the creating overlay for exactly this state.
    #[must_use]
    pub fn provision_in_flight(&self) -> bool {
        self.provision_pending.load(Ordering::SeqCst) || self.is_provisioning()
    }

    /// Create the first-run workspace (worker thread — blocking). Called from
    /// `begin_provision`'s worker and directly by tests.
    ///
    /// Single attempt, bounded, no retry: an invalid name is refused in Rust
    /// (mirroring the audited Python rule) so no child process is even spawned,
    /// and every CLI failure maps to the launcher's own finite code. On success
    /// the caller continues into the ordinary cold start, so provisioning is
    /// one continuous first-run journey rather than a second user action.
    ///
    /// Non-destructive by construction: the launcher's `provision` subcommand
    /// refuses to overwrite an existing `local-runtime.json`, so an existing
    /// workspace is never reseeded. This method also refuses to run at all once
    /// this process has created a workspace.
    pub fn provision_first_run(&self, raw_name: &str) -> Result<(), String> {
        let trimmed = self.validate_create_request(raw_name)?;
        let Some(paths) = self.paths.clone() else {
            // Unreachable (the validator refuses without a package), but fail
            // closed rather than spawning with no resolved paths.
            self.set_failure(
                LifecycleState::Failed,
                "RUNTIME_PACKAGE_MISSING".to_string(),
                None,
            );
            return Err("RUNTIME_PACKAGE_MISSING".to_string());
        };
        self.set_state(LifecycleState::Starting, None);
        if self.cancel_requested() {
            // The window is closing (or a cancel was requested) before this
            // worker reached its spawn: do not create a writer at all.
            self.set_state(LifecycleState::Stopped, None);
            return Err("PROVISION_CANCELLED".to_string());
        }
        let Ok(child) = paths.spawn_provision(&trimmed) else {
            self.set_failure(
                LifecycleState::Failed,
                "PROVISION_SPAWN_FAILED".to_string(),
                None,
            );
            return Err("PROVISION_SPAWN_FAILED".to_string());
        };
        *self
            .provision_child
            .lock()
            .unwrap_or_else(|e| e.into_inner()) = Some(child);
        let deadline = Instant::now() + PROVISION_DEADLINE;
        loop {
            if self.cancel_requested() {
                self.cancel_owned_provision();
                self.set_state(LifecycleState::Stopped, None);
                return Err("PROVISION_CANCELLED".to_string());
            }
            let exited = {
                let mut guard = self
                    .provision_child
                    .lock()
                    .unwrap_or_else(|e| e.into_inner());
                match guard.as_mut() {
                    Some(child) => match child.try_wait() {
                        Ok(Some(_)) => true,
                        Ok(None) => false,
                        Err(_) => {
                            // The child handle cannot be observed any more:
                            // stop it and report the finite code rather than
                            // waiting out the whole bound.
                            drop(guard);
                            self.cancel_owned_provision();
                            self.set_failure(
                                LifecycleState::Failed,
                                "PROVISION_WAIT_FAILED".to_string(),
                                None,
                            );
                            return Err("PROVISION_WAIT_FAILED".to_string());
                        }
                    },
                    // Taken by the close path: creation was cancelled.
                    None => return Err("PROVISION_CANCELLED".to_string()),
                }
            };
            if exited {
                let taken = self
                    .provision_child
                    .lock()
                    .unwrap_or_else(|e| e.into_inner())
                    .take();
                let Some(child) = taken else {
                    return Err("PROVISION_CANCELLED".to_string());
                };
                let Ok(output) = child.wait_with_output() else {
                    self.set_failure(
                        LifecycleState::Failed,
                        "PROVISION_OUTPUT_UNREADABLE".to_string(),
                        None,
                    );
                    return Err("PROVISION_OUTPUT_UNREADABLE".to_string());
                };
                if output.status.success() {
                    // Provisioning is complete; this process owns the workspace
                    // now. Nothing was reseeded or overwritten: the launcher's
                    // own `provision` refuses an existing configuration.
                    self.first_run.store(false, Ordering::SeqCst);
                    return Ok(());
                }
                let code = provision_failure_code(&String::from_utf8_lossy(&output.stderr));
                self.set_failure(LifecycleState::Failed, code.clone(), None);
                return Err(code);
            }
            if Instant::now() >= deadline {
                self.cancel_owned_provision();
                self.set_failure(
                    LifecycleState::Failed,
                    "PROVISION_TIMEOUT".to_string(),
                    None,
                );
                return Err("PROVISION_TIMEOUT".to_string());
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    }

    /// Whether a workspace creation is currently in flight.
    #[must_use]
    pub fn is_provisioning(&self) -> bool {
        self.provision_child
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .is_some()
    }

    /// Cancel an in-flight workspace creation by stopping exactly the owned
    /// `provision` child (kill + bounded reap). Used by the close path so a
    /// window close during creation never leaves a half-writing process behind;
    /// no foreign process is ever signalled and the data root is left exactly
    /// as the launcher wrote it.
    ///
    /// Safe interruption boundary: every provisioning write is atomic per file
    /// (`atomic_write`: temp file + fsync + `os.replace`), the launcher refuses
    /// to overwrite an existing workspace record, and the app deletes nothing
    /// and never recreates a record. A cancelled creation therefore leaves
    /// either a complete record (the next launch opens it) or no record (the
    /// next launch offers the create card) — never a partial or invalid one.
    pub fn cancel_owned_provision(&self) {
        let taken = self
            .provision_child
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .take();
        if let Some(mut child) = taken {
            let _ = child.kill();
            let deadline = Instant::now() + Duration::from_secs(10);
            while matches!(child.try_wait(), Ok(None)) && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(50));
            }
            let _ = child.wait();
        }
    }

    /// Cancel a `starting` tree: promptly terminate the owned supervisor child
    /// (still inside its ordered start; `stop.json` is only consumed once
    /// supervising), letting its Job Object backstop reap the partially
    /// started owned tree. Releases locks/ports, retains data.
    pub fn cancel_start(&self) {
        if let Some(paths) = self.paths.as_ref() {
            let mut guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
            if let Some(supervisor) = guard.as_mut() {
                supervisor.observe_runtime_identity(paths);
            }
        }
        self.stop_owned_prompt();
        if self.state() == LifecycleState::Starting {
            self.set_state(LifecycleState::Stopped, None);
        }
    }


    /// Ordinary app close: atomically request reverse-order stop for the
    /// confirmed owner identity, then release locks/ports and retain all data.
    /// An unowned child is only reaped as this instance's own process.
    pub fn shutdown(&self) -> bool {
        self.request_cancel();
        self.cancel_owned_provision();
        self.join_provision_worker();
        self.join_startup_worker();
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

    /// User-initiated Start from the lifecycle surface: a single bounded
    /// attempt through the existing `start` operation.
    ///
    /// Refused without any state change when a start is already running or the
    /// tree is already ready (no silent second attempt and no empty success
    /// screen), and when the data root is still awaiting workspace creation
    /// (the inline create card owns that path). Returns whether a start was begun.
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

    /// User-initiated Stop from the lifecycle surface. Runs the manager's own
    /// reverse-order shutdown on the calling thread (callers must not block the
    /// window): during `starting` it is the bounded mid-start cancel;
    /// afterwards it is the graceful `stop` request with the manager's own
    /// timeouts.
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
        self.request_cancel();
        self.cancel_owned_provision();
        self.join_provision_worker();
        self.join_startup_worker();
        let outcome = if self.state() == LifecycleState::Starting {
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
        let identity = {
            let mut guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
            let Some(supervisor) = guard.as_mut() else {
                return StopOutcome::Stopped;
            };
            if !supervisor.is_running() {
                guard.take();
                return StopOutcome::Stopped;
            }
            let Some(identity) = supervisor.runtime_identity().cloned() else {
                drop(guard);
                self.stop_owned_prompt();
                return StopOutcome::Stopped;
            };
            identity
        };
        if let Err(error) = paths.request_stop(&identity) {
            self.set_failure(
                LifecycleState::ShutdownFailed,
                error.failure_code().to_string(),
                None,
            );
            return StopOutcome::ShutdownFailed;
        }
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
            if let Some(status) = paths.read_runtime_status() {
                let same_runtime = status.runtime_id.as_deref()
                    == Some(identity.runtime_id.as_str())
                    && status.manager_pid == Some(identity.manager_pid);
                if same_runtime && status.state.as_deref() == Some("shutdown-failed") {
                    let code = status
                        .failure
                        .map(|record| record.code)
                        .unwrap_or_else(|| "GRACEFUL_STOP_TIMEOUT".to_string());
                    self.set_failure(LifecycleState::ShutdownFailed, code, None);
                    return StopOutcome::ShutdownFailed;
                }
            }
            if Instant::now() >= deadline {
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
        let runtime_identity = self
            .supervisor
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .as_ref()
            .and_then(|supervisor| supervisor.runtime_identity().cloned());
        let (code, service) = self.reap_supervisor_failure();
        let status_state = runtime_identity.and_then(|identity| {
            self.paths
                .as_ref()
                .and_then(LifecyclePaths::read_runtime_status)
                .filter(|status| {
                    status.runtime_id.as_deref() == Some(identity.runtime_id.as_str())
                        && status.manager_pid == Some(identity.manager_pid)
                })
                .and_then(|status| status.state)
        });
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
            // Mid-start cancellation terminates only this exact supervisor
            // child; its Job Object backstop reaps any services it started.
            if let Some(paths) = paths.as_ref() {
                supervisor.observe_runtime_identity(paths);
            }
            if supervisor.kill_and_reap(Duration::from_secs(30)) {
                guard.take();
            }
            return;
        }
        let Some(identity) = supervisor.runtime_identity().cloned() else {
            // The child has not proved that it owns the shared tree. It is safe
            // to reap this exact child, but never to request a shared-root stop.
            if supervisor.kill_and_reap(Duration::from_secs(30)) {
                guard.take();
            }
            return;
        };
        let Some(paths) = paths else {
            if supervisor.kill_and_reap(Duration::from_secs(10)) {
                guard.take();
            }
            return;
        };
        drop(guard);
        if paths.request_stop(&identity).is_err() {
            guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
            if let Some(supervisor) = guard.as_mut() {
                if supervisor.kill_and_reap(Duration::from_secs(10)) {
                    guard.take();
                }
            }
            return;
        }
        guard = self.supervisor.lock().unwrap_or_else(|e| e.into_inner());
        let Some(supervisor) = guard.as_mut() else {
            return;
        };
        if supervisor.wait_exit(timeout) {
            guard.take();
            return;
        }
        if supervisor.kill_and_reap(Duration::from_secs(10)) {
            let still_there = guard.take();
            drop(still_there);
            drop(guard);
            self.set_failure(
                self.state(),
                "GRACEFUL_STOP_TIMEOUT".to_string(),
                self.failure_service(),
            );
        }
    }
}
#[cfg(test)]
mod lifecycle_tests {
    use super::{
        BOOTSTRAP_SCHEME, BOOTSTRAP_SURFACE_URL, DEFAULT_API_PORT, FailureRecord, InitObservations,
        LOOPBACK_HOST, LifecycleController, LifecyclePaths, LifecycleState, ManagementView,
        OverlayMode, Readiness, StepStatus, StopOutcome, WorkspaceRecord, absolute_directory,
        api_origin, bootstrap_url, build_init_steps, download_destination, escape_html,
        extract_failure_code, external_link_allowed, is_allowed_navigation, is_finite_code,
        is_service_name, main_window_url, new_window_allowed, overlay_html, poll_api_ready,
        probe_api_readiness, render_workspace_management, validate_workspace_name,
        ThemeMode, UiPreferences,
    };

    /// Build a management view with no live observations, so a rendering test
    /// is deterministic on any host: the steps depend only on the state and
    /// failure record passed here.
    fn test_view(
        state: LifecycleState,
        failure: Option<FailureRecord>,
        supervisor_pid: Option<u32>,
        stop_pending: bool,
        start_pending: bool,
    ) -> ManagementView {
        let observations = InitObservations {
            package_resolved: true,
            supervisor_alive: supervisor_pid.is_some() || state == LifecycleState::Ready,
            ..InitObservations::default()
        };
        ManagementView {
            state,
            workspace: WorkspaceRecord::Active {
                name: "Team Notes".to_string(),
                project_id: "team-notes".to_string(),
            },
            steps: build_init_steps(state, failure.as_ref(), &observations),
            failure,
            api_origin: format!("http://{LOOPBACK_HOST}:{DEFAULT_API_PORT}/"),
            supervisor_pid,
            start_pending,
            stop_pending,
            provision_pending: false,
            can_start: matches!(
                state,
                LifecycleState::Stopped | LifecycleState::Failed | LifecycleState::Degraded
            ) && supervisor_pid.is_none()
                && !start_pending,
            first_run: false,
            refusal: None,
            theme_mode: ThemeMode::System,
        }
    }

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
        // The ready SPA's own desktop-only `Manage workspace` action navigates
        // the same window to the surface root; that exact URL must stay
        // admissible, or the management surface would become unreachable from
        // the ready workspace.
        let surface_root: url::Url = BOOTSTRAP_SURFACE_URL.parse().expect("valid surface root");
        assert_eq!(surface_root.as_str(), "http://projecta-bootstrap.localhost/");
        assert!(is_allowed_navigation(&surface_root, &origin));
        let explicit_default_port: url::Url =
            "http://projecta-bootstrap.localhost:80/provision?intent=create&name=X"
                .parse()
                .expect("valid default-port workaround URL");
        assert!(is_allowed_navigation(&explicit_default_port, &origin));
    }

    #[test]
    fn main_window_opens_exactly_the_bundled_bootstrap_surface() {
        let target = main_window_url();
        assert_eq!(target.scheme(), BOOTSTRAP_SCHEME);
        assert_eq!(target.host_str(), Some("localhost"));
        assert!(target.port().is_none());
        assert!(target.username().is_empty());
        assert!(target.password().is_none());
    }

    #[test]
    fn no_secondary_window_is_ever_allowed() {
        for raw in [
            "https://example.test/",
            "http://example.test/",
            "http://127.0.0.1:18732/",
            "http://localhost:18732/",
            "file:///C:/Windows/win.ini",
        ] {
            let url: url::Url = raw.parse().expect("valid URL");
            assert!(!new_window_allowed(&url), "must refuse a new window for {raw}");
        }
    }

    #[test]
    fn only_absolute_web_urls_are_external_links() {
        // Explicit external links are handed to the system browser: absolute
        // http/https destinations, including third-party origins and foreign
        // loopback ports the privileged view refuses to navigate to.
        for raw in [
            "https://example.test/",
            "http://example.test/",
            "https://example.test/path?a=1&b=2#frag",
            "http://127.0.0.1:18999/probe",
            "http://127.0.0.1:18080/",
        ] {
            let url: url::Url = raw.parse().expect("valid URL");
            assert!(external_link_allowed(&url), "must allow external link {raw}");
        }
        // Everything else stays inside the app boundary: no scheme hand-off
        // for local files, data or script URLs, app custom schemes, or
        // about:. A relative reference never reaches this hand-off: it
        // resolves inside the page that produced it.
        for raw in [
            "file:///C:/Windows/win.ini",
            "data:text/html,<b>x</b>",
            "javascript:alert(1)",
            "projecta-bootstrap://localhost/",
            "tauri://localhost/",
            "about:blank",
            "mailto:someone@example.test",
        ] {
            let url: url::Url = raw.parse().expect("valid URL");
            assert!(
                !external_link_allowed(&url),
                "must refuse external link {raw}"
            );
        }
    }

    #[test]
    fn download_destination_preserves_the_requested_file_name() {
        let root = disposable_root("s15-07-download-destination");
        let default = root.join("s15-07-export-projecta-export-1234.projecta");
        // A disposable root moves the archive there and keeps the exact name
        // the page requested.
        let target = download_destination(&default, Some(&root)).expect("owned destination");
        assert_eq!(target, root.join("s15-07-export-projecta-export-1234.projecta"));
        // Without an override the platform's own destination is used.
        assert_eq!(download_destination(&default, None), None);
        // A destination the host cannot create is refused rather than failing
        // the download (the platform default stays in place): an existing
        // regular file can never become a directory.
        let blocker = root.join("blocker");
        std::fs::write(&blocker, b"not a directory").expect("write blocker");
        let unusable = blocker.join("sub");
        assert_eq!(download_destination(&default, Some(&unusable)), None);
        // A destination with no file name cannot be rewritten.
        assert_eq!(
            download_destination(std::path::Path::new("C:/"), Some(&root)),
            None
        );
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn only_absolute_directories_are_honoured() {
        assert_eq!(
            absolute_directory("F:/ai-ml/projecta/build/owned"),
            Some(std::path::PathBuf::from("F:/ai-ml/projecta/build/owned"))
        );
        for refused in ["", "relative/dir", "./relative", "F:relative"] {
            assert_eq!(absolute_directory(refused), None, "must refuse {refused:?}");
        }
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
    fn live_states_refresh_and_terminal_states_do_not() {
        let starting = render_workspace_management(&test_view(
            LifecycleState::Starting,
            None,
            Some(1234),
            false,
            false,
        ));
        // No script surface is introduced (CSP `script-src` is unchanged and
        // the surface is server-rendered HTML).
        assert!(!starting.contains("<script"));
        // Starting cannot start again (no second tree) but can be cancelled:
        // both controls keep their real, actionable state.
        assert!(starting.contains("data-testid=\"lifecycle-start\" disabled"));
        assert!(!starting.contains("data-testid=\"lifecycle-stop\" disabled"));
        // A state that can still change by itself refreshes the view, and the
        // refresh target is the exact bundled origin the guard accepts.
        assert!(starting.contains("http-equiv=\"refresh\""));
        assert!(starting.contains(BOOTSTRAP_SURFACE_URL));

        let stopped = render_workspace_management(&test_view(
            LifecycleState::Stopped,
            None,
            None,
            false,
            false,
        ));
        // Stopped is the recovery entry point: Start enabled, Stop meaningless.
        assert!(!stopped.contains("data-testid=\"lifecycle-start\" disabled"));
        assert!(stopped.contains("data-testid=\"lifecycle-stop\" disabled"));
        // A terminal state never auto-refreshes: nothing retries by itself.
        assert!(!stopped.contains("http-equiv=\"refresh\""));
    }

    #[test]
    fn startup_overlay_covers_only_the_real_in_flight_action() {
        // A runtime start in flight renders the distinct overlay above the
        // management shell: same real step model, its own cancel binding, and
        // the page's own live refresh. No timer, no percentage, no progress
        // element.
        let starting = render_workspace_management(&test_view(
            LifecycleState::Starting,
            None,
            Some(1234),
            false,
            false,
        ));
        assert!(starting.contains("data-testid=\"startup-overlay\""));
        assert!(starting.contains("data-overlay-mode=\"starting\""));
        assert!(starting.contains("data-testid=\"overlay-stop\""));
        assert!(starting.contains("http-equiv=\"refresh\""));
        assert!(starting.contains(BOOTSTRAP_SURFACE_URL));
        assert!(!starting.contains("<progress"));
        // The shell below the overlay is inert: covered controls cannot take
        // focus, while the overlay's own cancel binding stays reachable.
        assert!(starting.contains("<main class=\"shell-main\" inert>"));
        // The overlay's own body carries the real observed steps (shared with
        // the shell table) and never a projected one.
        let starting_view = test_view(LifecycleState::Starting, None, Some(1234), false, false);
        let overlay = overlay_html(&starting_view);
        assert!(overlay.contains("data-testid=\"init-step-package\""));
        assert!(overlay.contains("data-testid=\"init-step-supervisor\""));
        // The overlay's summary is the same real count as the step model.
        let done = starting_view
            .steps
            .iter()
            .filter(|step| step.status == StepStatus::Done)
            .count();
        assert!(overlay.contains(&format!("{done} of 8 steps done")));

        // Every state that cannot change by itself renders the management
        // surface alone — recovery, diagnostics, and typed input stay
        // reachable with no overlay layer.
        for (state, pid) in [
            (LifecycleState::Ready, Some(4321)),
            (LifecycleState::Failed, None),
            (LifecycleState::Stopped, None),
            (LifecycleState::Bootstrap, None),
            (LifecycleState::ShutdownFailed, None),
            (LifecycleState::Degraded, None),
        ] {
            let html = render_workspace_management(&test_view(state, None, pid, false, false));
            assert!(
                !html.contains("data-testid=\"startup-overlay\""),
                "no overlay in state {}",
                state.as_str()
            );
            assert!(
                !html.contains("inert"),
                "the management shell stays reachable in {}",
                state.as_str()
            );
        }
    }

    #[test]
    fn creating_overlay_covers_the_create_action_and_claims_no_service_step() {
        // The create submission is accepted synchronously and renders this
        // overlay from the first render: `starting` with a create in flight.
        let view = ManagementView {
            first_run: true,
            provision_pending: true,
            workspace: WorkspaceRecord::Absent,
            ..test_view(LifecycleState::Starting, None, None, false, false)
        };
        assert_eq!(view.overlay(), Some(OverlayMode::Creating));
        let html = render_workspace_management(&view);
        assert!(html.contains("data-overlay-mode=\"creating\""));
        // The overlay itself claims no service step: no service starts before
        // the workspace exists, so it carries no step table at all.
        let overlay = overlay_html(&view);
        assert!(overlay.contains("Creating your local workspace"));
        assert!(!overlay.contains("data-testid=\"init-step-"));
        assert!(!overlay.contains("<table"));
        // The card behind it is locked for exactly this real state, and the
        // page keeps refreshing to the real outcome.
        assert!(html.contains("data-testid=\"first-run-create\" disabled"));
        assert!(html.contains("http-equiv=\"refresh\""));
        // A workspace that exists is never covered by the creating overlay.
        let existing = ManagementView {
            first_run: false,
            provision_pending: false,
            ..view.clone()
        };
        assert_eq!(existing.overlay(), Some(OverlayMode::Starting));
    }

    #[test]
    fn first_run_failure_points_back_to_the_create_form_not_a_start_retry() {
        let failure = FailureRecord::new("PROVISION_TIMEOUT".to_string(), None);
        let view = ManagementView {
            first_run: true,
            workspace: WorkspaceRecord::Absent,
            ..test_view(LifecycleState::Failed, Some(failure), None, false, false)
        };
        let html = render_workspace_management(&view);
        assert!(html.contains("PROVISION_TIMEOUT"));
        assert!(html.contains("submit the create form again"));
        assert!(!html.contains("then Retry startup for one bounded attempt"));
        // No overlay over a failure: the surface, its diagnostics, and the
        // create form must be usable.
        assert!(!html.contains("data-testid=\"startup-overlay\""));
    }

    #[test]
    fn ready_surface_marks_every_step_done_and_opens_the_workspace() {
        let view = ManagementView {
            can_start: false,
            ..test_view(LifecycleState::Ready, None, Some(4321), false, false)
        };
        // A ready tree has observed every dependency: no step may stay pending,
        // active, or failed once readiness is real.
        assert!(
            view.steps
                .iter()
                .all(|step| step.status == StepStatus::Done),
            "a ready tree has observed every dependency"
        );
        let html = render_workspace_management(&view);
        // The second top-level surface is reachable from the management surface
        // exactly when the runtime is objectively ready.
        assert!(!html.contains("data-testid=\"lifecycle-open\" disabled"));
        let not_ready = render_workspace_management(&test_view(
            LifecycleState::Stopped,
            None,
            None,
            false,
            false,
        ));
        assert!(not_ready.contains("data-testid=\"lifecycle-open\" disabled"));
    }

    #[test]
    fn steps_never_claim_more_than_they_observed() {
        // Nothing observed beyond the resolved package: the remaining steps are
        // pending or active, never done, and no failure is invented.
        let observations = InitObservations {
            package_resolved: true,
            ..InitObservations::default()
        };
        let steps = build_init_steps(LifecycleState::Starting, None, &observations);
        assert_eq!(steps.len(), 8);
        assert_eq!(steps[0].status, StepStatus::Done);
        assert_eq!(steps[1].status, StepStatus::Active);
        assert_eq!(
            steps
                .iter()
                .filter(|step| step.status == StepStatus::Done)
                .count(),
            1
        );
        // A real observation flips exactly its own step.
        let observations = InitObservations {
            package_resolved: true,
            supervisor_alive: true,
            postgres_listening: true,
            ..InitObservations::default()
        };
        let steps = build_init_steps(LifecycleState::Starting, None, &observations);
        assert_eq!(steps[0].status, StepStatus::Done);
        assert_eq!(steps[1].status, StepStatus::Done);
        assert_eq!(steps[2].status, StepStatus::Done);
        assert_eq!(steps[3].status, StepStatus::Active);
        assert_eq!(steps[4].status, StepStatus::Pending);
    }

    #[test]
    fn failed_dependency_marks_its_own_step() {
        let observations = InitObservations {
            package_resolved: true,
            supervisor_alive: true,
            postgres_listening: true,
            ..InitObservations::default()
        };
        let failure = FailureRecord::new("PORT_IN_USE".to_string(), Some("fuseki".to_string()));
        let steps = build_init_steps(LifecycleState::Failed, Some(&failure), &observations);
        let fuseki = steps
            .iter()
            .find(|step| step.key == "fuseki")
            .expect("fuseki step");
        assert_eq!(fuseki.status, StepStatus::Failed);
        let postgres = steps
            .iter()
            .find(|step| step.key == "postgres")
            .expect("postgres step");
        assert_eq!(postgres.status, StepStatus::Done);
        // A supervisor-level code blames the supervisor step, not a service.
        let supervisor_failure =
            FailureRecord::new("RUNTIME_ALREADY_ACTIVE".to_string(), None);
        let steps = build_init_steps(
            LifecycleState::Failed,
            Some(&supervisor_failure),
            &observations,
        );
        let supervisor = steps
            .iter()
            .find(|step| step.key == "supervisor")
            .expect("supervisor step");
        assert_eq!(supervisor.status, StepStatus::Failed);
        assert!(
            steps
                .iter()
                .filter(|step| step.status == StepStatus::Failed)
                .count()
                == 1,
            "only the blamed step fails"
        );
    }

    #[test]
    fn api_readiness_body_is_sanitized_and_reported() {
        // A real loopback responder: the probe must report the API's own
        // published fields and drop anything hostile.
        let listener = std::net::TcpListener::bind("127.0.0.1:0").expect("ephemeral port");
        let port = listener.local_addr().expect("local addr").port();
        let responder = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept");
            let mut scratch = [0u8; 1024];
            let _ = std::io::Read::read(&mut stream, &mut scratch);
            let body = "{\"status\":\"not-ready\",\"semanticCore\":\"ready\",\"oidc\":\"unavailable\",\"reasonCode\":\"OIDC_PROVIDER_UNAVAILABLE\",\"secret\":\"<script>alert(1)</script>\"}";
            let response = format!(
                "HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            );
            let _ = std::io::Write::write_all(&mut stream, response.as_bytes());
        });
        let readiness = probe_api_readiness(port, std::time::Duration::from_secs(5));
        responder.join().expect("responder thread");
        assert_eq!(readiness.http_status, Some(503));
        assert_eq!(readiness.status.as_deref(), Some("not-ready"));
        assert_eq!(readiness.semantic_core.as_deref(), Some("ready"));
        assert_eq!(readiness.oidc.as_deref(), Some("unavailable"));
        assert_eq!(readiness.reason_code.as_deref(), Some("OIDC_PROVIDER_UNAVAILABLE"));
        assert!(readiness.http_status != Some(200));
        // The unlisted field is not part of the view at all.
        let rendered = format!("{readiness:?}");
        assert!(!rendered.contains("script"));

        // A real 200 with the published ready body counts as ready.
        let listener = std::net::TcpListener::bind("127.0.0.1:0").expect("ephemeral port");
        let port = listener.local_addr().expect("local addr").port();
        let responder = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept");
            let mut scratch = [0u8; 1024];
            let _ = std::io::Read::read(&mut stream, &mut scratch);
            let body = "{\"status\":\"ready\",\"semanticCore\":\"ready\",\"oidc\":\"ready\"}";
            let response = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            );
            let _ = std::io::Write::write_all(&mut stream, response.as_bytes());
        });
        let readiness = probe_api_readiness(port, std::time::Duration::from_secs(5));
        responder.join().expect("responder thread");
        assert_eq!(readiness.http_status, Some(200));
        assert_eq!(readiness.oidc.as_deref(), Some("ready"));
        assert_eq!(
            poll_api_ready(port, std::time::Duration::from_secs(1)),
            // The listener is gone after one connection: a closed port is not
            // ready, which is the fail-closed direction.
            Readiness::ProbeFailed
        );
    }

    #[test]
    fn workspace_record_reading_is_sanitized() {
        let data_root = disposable_root("s15-07-ux-workspace-record");
        std::fs::create_dir_all(data_root.join("config")).expect("config dir");
        let paths = nonexistent_paths(&data_root);
        assert_eq!(paths.read_workspace_record(), WorkspaceRecord::Absent);
        std::fs::write(
            data_root.join("config/local-runtime.json"),
            serde_json::json!({
                "formatVersion": 1,
                "projectId": "team-notes",
                "projectName": "Team Notes",
                "actorId": "local-operator",
            })
            .to_string(),
        )
        .expect("write record");
        assert_eq!(
            paths.read_workspace_record(),
            WorkspaceRecord::Active {
                name: "Team Notes".to_string(),
                project_id: "team-notes".to_string(),
            }
        );
        // A hostile or malformed record never reaches the surface.
        std::fs::write(
            data_root.join("config/local-runtime.json"),
            serde_json::json!({
                "formatVersion": 1,
                "projectId": "<script>",
                "projectName": "bad\u{0}name",
            })
            .to_string(),
        )
        .expect("write hostile record");
        assert_eq!(paths.read_workspace_record(), WorkspaceRecord::Unreadable);
        std::fs::write(data_root.join("config/local-runtime.json"), "[]").expect("write array");
        assert_eq!(paths.read_workspace_record(), WorkspaceRecord::Unreadable);
        let _ = std::fs::remove_dir_all(&data_root);
    }

    #[test]
    fn create_card_is_inline_and_refuses_without_echoing_raw_text() {
        let view = ManagementView {
            first_run: true,
            refusal: Some("WORKSPACE_NAME_INVALID".to_string()),
            workspace: WorkspaceRecord::Absent,
            ..test_view(LifecycleState::Bootstrap, None, None, false, false)
        };
        let html = render_workspace_management(&view);
        // The finite refusal is rendered for the user.
        assert!(html.contains("WORKSPACE_NAME_INVALID"));
        // No script, no filesystem path, and no data-root file name is rendered.
        assert!(!html.contains("<script"));
        assert!(!html.contains("local-runtime.json"));
        assert!(!html.contains("C:\\"));
        assert!(!html.contains("C:/"));
        // Typed input must never be discarded by a self-refresh: the create
        // card is never live.
        assert!(!html.contains("http-equiv=\"refresh\""));
        // A hostile refusal code is refused rather than rendered.
        let hostile = ManagementView {
            refusal: Some("<script>alert(1)</script>".to_string()),
            ..view.clone()
        };
        let html = render_workspace_management(&hostile);
        assert!(!html.contains("alert(1)"));
    }

    #[test]
    fn unreadable_workspace_record_is_stated_finitely() {
        let view = ManagementView {
            workspace: WorkspaceRecord::Unreadable,
            ..test_view(LifecycleState::Failed, None, None, false, false)
        };
        let html = render_workspace_management(&view);
        // The finite code is stated and - critically - no creation request can
        // be submitted: the app never silently recreates an unreadable record.
        assert!(html.contains("LOCAL_PROJECT_CONFIGURATION_INVALID"));
        assert!(!html.contains("/provision"));
    }

    #[test]
    fn degraded_surface_names_the_failing_dependency_and_recovery() {
        let html = render_workspace_management(&ManagementView {
            failure: Some(FailureRecord::new(
                "SERVICE_BECAME_UNREADY".to_string(),
                Some("fuseki".to_string()),
            )),
            ..test_view(LifecycleState::Degraded, None, None, false, false)
        });
        // The failing dependency and its finite code are surfaced, never an
        // empty success screen, and recovery is offered but never automatic.
        assert!(html.contains("SERVICE_BECAME_UNREADY"));
        assert!(html.contains("fuseki"));
        assert!(!html.contains("http-equiv=\"refresh\""));
        assert!(!html.contains("data-testid=\"lifecycle-start\" disabled"));
    }

    #[test]
    fn shutdown_failed_surface_offers_the_explicit_stop_retry_only() {
        let html = render_workspace_management(&ManagementView {
            failure: Some(FailureRecord::new(
                "GRACEFUL_STOP_TIMEOUT".to_string(),
                None,
            )),
            // The manager is alive and waiting for its explicit stop retry: the
            // surface must keep offering Stop.
            supervisor_pid: Some(2222),
            ..test_view(LifecycleState::ShutdownFailed, None, None, false, false)
        });
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
        let html = render_workspace_management(&ManagementView {
            failure: Some(FailureRecord {
                code: "PORT_IN_USE".to_string(),
                service: None,
                detail: Some("api on port 18732".to_string()),
            }),
            ..test_view(LifecycleState::Failed, None, None, false, false)
        });
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
    fn stop_request_refuses_a_changed_runtime_identity() {
        let data_root = disposable_root("s15-07-owner-stop-identity");
        std::fs::create_dir_all(data_root.join("state")).expect("state directory");
        let paths = nonexistent_paths(&data_root);
        let runtime_id = "a".repeat(32);
        let identity = super::RuntimeIdentity {
            runtime_id: runtime_id.clone(),
            manager_pid: 1234,
        };
        let status_path = data_root.join("state/runtime.json");
        std::fs::write(
            &status_path,
            serde_json::json!({
                "runtimeId": runtime_id,
                "managerPid": identity.manager_pid,
                "state": "ready",
            })
            .to_string(),
        )
        .expect("write current owner status");

        assert_eq!(paths.request_stop(&identity), Ok(()));
        let stop_path = data_root.join("state/stop.json");
        let owner_request = std::fs::read(&stop_path).expect("identity-bound stop request");
        let request: serde_json::Value =
            serde_json::from_slice(&owner_request).expect("valid stop request");
        assert_eq!(
            request.get("runtimeId").and_then(serde_json::Value::as_str),
            Some(identity.runtime_id.as_str())
        );

        std::fs::write(
            &status_path,
            serde_json::json!({
                "runtimeId": "b".repeat(32),
                "managerPid": 4321,
                "state": "ready",
            })
            .to_string(),
        )
        .expect("replace with another runtime owner");
        assert_eq!(
            paths.request_stop(&identity),
            Err(super::StopRequestError::IdentityChanged)
        );
        assert_eq!(
            std::fs::read(&stop_path).expect("unchanged foreign stop request"),
            owner_request,
            "a stale identity never overwrites the shared stop request"
        );
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
        // An unprovisioned root never starts from the surface: the inline
        // create card owns that path.
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
        // not yet flipped the state, so the real outcome is always shown. The
        // render contract is asserted on a deterministic view: a controller
        // without a package finishes its attempt in microseconds.
        let in_flight = ManagementView {
            start_pending: true,
            can_start: false,
            ..test_view(LifecycleState::Bootstrap, None, None, false, true)
        };
        assert!(in_flight.is_live());
        let pending = render_workspace_management(&in_flight);
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
        // Feed a missing packaged supervisor path so the first start fails fast,
        // then verify a repeated start is still refused.
        let paths = LifecyclePaths {
            supervisor_exe: std::path::PathBuf::from("C:/nonexistent/ProjectaLocal.exe"),
            local_app_data: std::path::PathBuf::from("C:/nonexistent/localappdata"),
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

    #[cfg(windows)]
    #[test]
    fn closing_an_unowned_or_refused_instance_preserves_the_first_runtime() {
        let data_root = disposable_root("s15-07-ux-foreign-runtime");
        let _root_cleanup = TempRootCleanup(data_root.clone());
        prepare_runtime_root(&data_root);
        let first_runtime_id = "a".repeat(32);
        write_runtime_status(&data_root, &first_runtime_id, std::process::id(), "ready");
        let status_path = data_root.join("state/runtime.json");
        let original_status = std::fs::read(&status_path).expect("first runtime status");
        let lock_path = data_root.join("state/runtime.lock");
        let mut first_lock = open_exclusive_test_lock(&lock_path);
        let original_lock = read_test_lock(&mut first_lock);
        let first_api = TestHealthServer::start(None);
        assert_eq!(
            poll_api_ready(first_api.port, std::time::Duration::from_secs(2)),
            Readiness::Ready
        );
        let script = write_supervisor_test_script(&data_root);
        let paths = test_lifecycle_paths(&data_root, &script);

        let pending = std::sync::Arc::new(LifecycleController::new(
            Some(paths.clone()),
            first_api.port,
        ));
        let _close_guard = ShutdownControllerOnDrop(std::sync::Arc::clone(&pending));
        pending.spawn_cold_start();
        wait_for_file(&data_root.join("started.txt"), "pending supervisor start");
        let pending_pid = pending
            .supervisor_pid()
            .expect("second manager child is owned");
        std::fs::write(data_root.join("go.txt"), "start descendant").expect("release pending child");
        let pending_child = wait_for_child_pid(&data_root.join("child.pid"));
        assert_supervisor_job_contains(&pending, pending_pid);
        assert_supervisor_job_contains(&pending, pending_child);
        assert_eq!(pending.state(), LifecycleState::Starting);
        assert!(
            !pending.owned_supervisor_alive(),
            "the first manager PID/status cannot confer ownership on this child"
        );
        assert!(
            pending.shutdown(),
            "closing the pending, unowned second controller should be prompt"
        );
        assert_process_exited(pending_child, &data_root, "powershell.exe");
        assert_process_exited(pending_pid, &data_root, "cmd.exe");
        assert!(!data_root.join("state/stop.json").exists());
        assert_eq!(std::fs::read(&status_path).expect("status after close"), original_status);
        assert_eq!(read_test_lock(&mut first_lock), original_lock);
        assert_test_lock_held(&lock_path);
        let server_thread_finished = first_api
            .thread
            .as_ref()
            .is_some_and(|thread| thread.is_finished());
        let server_stopped = first_api
            .stopped
            .load(std::sync::atomic::Ordering::Relaxed);
        let direct_connect = std::net::TcpStream::connect_timeout(
            &std::net::SocketAddr::from(([127, 0, 0, 1], first_api.port)),
            std::time::Duration::from_secs(1),
        )
        .map(|_| ());
        let first_api_after_close =
            poll_api_ready(first_api.port, std::time::Duration::from_secs(2));
        let server_error = first_api
            .accept_error
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .clone();
        assert_eq!(
            first_api_after_close,
            Readiness::Ready,
            "the first service listener must remain reachable after immediate close (stopped={server_stopped}, thread_finished={server_thread_finished}, accept_error={server_error:?}, direct_connect={direct_connect:?})"
        );

        // A distinct second launch that reaches the supervisor's refusal
        // reports the real finite failure; closing it still must not ask the
        // shared data root to stop whichever manager owns it.
        std::fs::remove_file(data_root.join("started.txt")).expect("clear start marker");
        std::fs::remove_file(data_root.join("go.txt")).expect("clear go marker");
        std::fs::remove_file(data_root.join("child.pid")).expect("clear child marker");
        let refused = std::sync::Arc::new(LifecycleController::new(
            Some(paths),
            first_api.port,
        ));
        let _close_guard = ShutdownControllerOnDrop(std::sync::Arc::clone(&refused));
        refused.spawn_cold_start();
        wait_for_file(&data_root.join("started.txt"), "refused supervisor start");
        let refused_pid = refused
            .supervisor_pid()
            .expect("refused manager child is owned");
        std::fs::write(data_root.join("go.txt"), "start descendant").expect("release refused child");
        let refused_child = wait_for_child_pid(&data_root.join("child.pid"));
        assert_supervisor_job_contains(&refused, refused_pid);
        assert_supervisor_job_contains(&refused, refused_child);
        std::fs::write(data_root.join("refuse.txt"), "RUNTIME_ALREADY_ACTIVE")
            .expect("release supervisor refusal");
        refused.join_startup_worker();
        assert_eq!(refused.state(), LifecycleState::Failed);
        assert_eq!(
            refused.failure_code().as_deref(),
            Some("RUNTIME_ALREADY_ACTIVE")
        );
        assert_process_exited(refused_child, &data_root, "powershell.exe");
        assert_process_exited(refused_pid, &data_root, "cmd.exe");
        assert!(refused.shutdown());
        assert!(!data_root.join("state/stop.json").exists());
        assert_eq!(std::fs::read(&status_path).expect("status after refusal"), original_status);
        assert_eq!(read_test_lock(&mut first_lock), original_lock);
        assert_test_lock_held(&lock_path);
        assert_eq!(
            poll_api_ready(first_api.port, std::time::Duration::from_secs(2)),
            Readiness::Ready,
            "a refused second launch must leave the first listener and lock intact"
        );

        drop(first_lock);
        first_api.stop();
        let _ = std::fs::remove_dir_all(&data_root);
    }

    #[cfg(windows)]
    #[test]
    fn owned_supervisor_is_assigned_to_its_kill_on_close_job() {
        let data_root = disposable_root("s15-07-ux-job-membership");
        let _root_cleanup = TempRootCleanup(data_root.clone());
        prepare_runtime_root(&data_root);
        let script = write_supervisor_test_script(&data_root);
        let controller = std::sync::Arc::new(LifecycleController::new(
            Some(test_lifecycle_paths(&data_root, &script)),
            closed_loopback_port(),
        ));
        let _close_guard = ShutdownControllerOnDrop(std::sync::Arc::clone(&controller));
        controller.spawn_cold_start();
        wait_for_file(&data_root.join("started.txt"), "job membership supervisor start");
        let manager_pid = controller.supervisor_pid().expect("owned manager child PID");
        let membership = {
            let guard = controller
                .supervisor
                .lock()
                .unwrap_or_else(|error| error.into_inner());
            let supervisor = guard.as_ref().expect("owned supervisor exists");
            supervisor._job.contains_process(manager_pid)
        };
        assert_eq!(
            membership,
            super::JobMembership::InJob(true),
            "exact manager PID {manager_pid} must belong to the supervisor's kill-on-close job"
        );
        assert!(controller.shutdown(), "job membership fixture shuts down cleanly");
        assert_process_exited(manager_pid, &data_root, "cmd.exe");
    }

    #[cfg(windows)]
    #[test]
    fn owned_job_identity_rejects_foreign_same_image_and_wrong_parent_workers() {
        let data_root = disposable_root("s15-13-job-identity");
        let _root_cleanup = TempRootCleanup(data_root.clone());
        let executable = std::env::current_exe().expect("test executable path");
        let mut launch = TaskChildCleanup(
            std::process::Command::new(&executable)
                .arg("job_identity_fixture_root")
                .arg("--nocapture")
                .env("PROJECTA_S15_JOB_ROOT", &data_root)
                .spawn()
                .expect("spawn task-owned launch fixture"),
        );
        let job = match super::JobGuard::assign(super::raw_handle_of(&launch.0)) {
            Ok(job) => job,
            Err(error) => {
                let _ = launch.0.kill();
                let _ = launch.0.wait();
                panic!("assign test launch to owned job: {error}");
            }
        };
        std::fs::write(data_root.join("start"), b"start worker")
            .expect("release task-owned worker fixture");
        let worker_ready = data_root.join("worker.ready");
        wait_for_file(&data_root.join("worker.pid"), "same-image worker PID");
        wait_for_file(&worker_ready, "same-image worker readiness");
        let worker_pid = std::fs::read_to_string(data_root.join("worker.pid"))
            .expect("read same-image worker PID")
            .trim()
            .parse::<u32>()
            .expect("parse same-image worker PID");
        let mut image_buffer = vec![0_u16; 32_768];
        let worker_membership = job.contains_process(worker_pid);
        let direct_worker_accepted = job.contains_supervisor_process(
            worker_pid,
            launch.0.id(),
            &executable,
            &mut image_buffer,
        );
        let wrong_parent_accepted = job.contains_supervisor_process(
            worker_pid,
            std::process::id(),
            &executable,
            &mut image_buffer,
        );

        let outside_ready = data_root.join("outside.ready");
        let outside = TaskChildCleanup(
            std::process::Command::new(&executable)
                .arg("job_identity_fixture_worker")
                .arg("--nocapture")
                .env("PROJECTA_S15_JOB_WORKER", "1")
                .env("PROJECTA_S15_JOB_WORKER_READY", &outside_ready)
                .spawn()
                .expect("spawn same-image worker outside owned job"),
        );
        wait_for_file(&outside_ready, "outside-job same-image worker readiness");
        let outside_membership = job.contains_process(outside.0.id());
        let outside_worker_accepted = job.contains_supervisor_process(
            outside.0.id(),
            launch.0.id(),
            &executable,
            &mut image_buffer,
        );
        drop(outside);
        drop(job);
        let _ = launch.0.wait();

        assert_eq!(
            worker_membership,
            super::JobMembership::InJob(true),
            "the direct worker must be in this launch's owned job"
        );
        assert!(
            direct_worker_accepted,
            "the exact direct worker with the packaged image is accepted"
        );
        assert!(
            !wrong_parent_accepted,
            "an in-job same-image process with another parent is not the worker"
        );
        assert_eq!(
            outside_membership,
            super::JobMembership::InJob(false),
            "the foreign same-image worker is outside this launch's owned job"
        );
        assert!(
            !outside_worker_accepted,
            "same image and PID existence outside the job never establish ownership"
        );
    }

    #[cfg(windows)]
    #[test]
    fn supervisor_refuses_reused_runtime_id_from_its_launched_child() {
        let data_root = disposable_root("s15-13-stale-runtime-id");
        let _root_cleanup = TempRootCleanup(data_root.clone());
        prepare_runtime_root(&data_root);
        let script = write_supervisor_test_script(&data_root);
        let paths = test_lifecycle_paths(&data_root, &script);
        let previous_runtime_id = "d".repeat(32);
        let mut supervisor = super::OwnedSupervisor::spawn(
            &script,
            &paths.local_app_data,
            Some(previous_runtime_id.clone()),
        )
        .expect("spawn task-owned supervisor fixture");
        write_runtime_status(
            &data_root,
            &previous_runtime_id,
            supervisor.pid(),
            "ready",
        );

        let accepted = supervisor.observe_runtime_identity(&paths);
        let adopted_identity = supervisor.runtime_identity().cloned();
        let reaped = supervisor.kill_and_reap(std::time::Duration::from_secs(10));

        assert!(!accepted, "a prior runtime ID is never adopted again");
        assert!(
            adopted_identity.is_none(),
            "the stale runtime record does not become an owned identity"
        );
        assert!(reaped, "the task-owned launched child is reaped");
    }

    #[cfg(windows)]
    #[test]
    fn job_identity_fixture_worker() {
        if std::env::var_os("PROJECTA_S15_JOB_WORKER").is_none() {
            return;
        }
        let ready = std::env::var_os("PROJECTA_S15_JOB_WORKER_READY")
            .expect("worker readiness path");
        std::fs::write(ready, b"ready").expect("write worker readiness");
        loop {
            std::thread::sleep(std::time::Duration::from_secs(1));
        }
    }

    #[cfg(windows)]
    #[test]
    fn job_identity_fixture_root() {
        let Some(root) = std::env::var_os("PROJECTA_S15_JOB_ROOT") else {
            return;
        };
        let root = std::path::PathBuf::from(root);
        while !root.join("start").is_file() {
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        let worker_ready = root.join("worker.ready");
        let worker = std::process::Command::new(
            std::env::current_exe().expect("test executable path"),
        )
        .arg("job_identity_fixture_worker")
        .arg("--nocapture")
        .env("PROJECTA_S15_JOB_WORKER", "1")
        .env("PROJECTA_S15_JOB_WORKER_READY", &worker_ready)
        .spawn()
        .expect("spawn same-image child worker");
        std::fs::write(root.join("worker.pid"), worker.id().to_string())
            .expect("write same-image worker PID");
        loop {
            std::thread::sleep(std::time::Duration::from_secs(1));
        }
    }
    #[cfg(windows)]
    #[test]
    fn cancelling_after_own_runtime_identity_kills_only_its_startup_tree() {
        let data_root = disposable_root("s15-07-ux-owned-start-cancel");
        let _root_cleanup = TempRootCleanup(data_root.clone());
        prepare_runtime_root(&data_root);
        write_runtime_status(&data_root, &"b".repeat(32), std::process::id(), "stopped");
        let api_port = closed_loopback_port();
        let script = write_supervisor_test_script(&data_root);
        let controller = std::sync::Arc::new(LifecycleController::new(
            Some(test_lifecycle_paths(&data_root, &script)),
            api_port,
        ));
        let _close_guard = ShutdownControllerOnDrop(std::sync::Arc::clone(&controller));
        controller.spawn_cold_start();
        wait_for_file(&data_root.join("started.txt"), "owned supervisor start");
        let manager_pid = controller.supervisor_pid().expect("owned manager child PID");
        std::fs::write(data_root.join("go.txt"), "start owned descendant")
            .expect("release owned child");
        let owned_child = wait_for_child_pid(&data_root.join("child.pid"));
        assert_supervisor_job_contains(&controller, manager_pid);
        assert_supervisor_job_contains(&controller, owned_child);
        let runtime_id = "c".repeat(32);
        write_runtime_status(&data_root, &runtime_id, manager_pid, "starting");
        wait_until(
            || controller.owned_supervisor_alive(),
            "fresh manager identity adoption",
        );
        assert_eq!(controller.state(), LifecycleState::Starting);

        assert!(
            controller.shutdown(),
            "close during successful startup cancels and joins the real owned child"
        );
        assert!(!controller.has_supervisor());
        assert_process_exited(manager_pid, &data_root, "cmd.exe");
        assert_process_exited(owned_child, &data_root, "powershell.exe");
        assert!(!data_root.join("state/stop.json").exists());
        let status = std::fs::read_to_string(data_root.join("state/runtime.json"))
            .expect("runtime status after owned cancellation");
        assert!(status.contains(&runtime_id));
        assert!(!controller.owned_supervisor_alive());
        let _ = std::fs::remove_dir_all(&data_root);
    }

    #[cfg(windows)]
    #[test]
    fn ready_owner_stop_passes_its_runtime_identity_and_stops_only_its_services() {
        let data_root = disposable_root("s15-07-ux-owned-stop");
        let _root_cleanup = TempRootCleanup(data_root.clone());
        prepare_runtime_root(&data_root);
        write_runtime_status(&data_root, &"d".repeat(32), std::process::id(), "stopped");
        let script = write_supervisor_test_script(&data_root);
        let stop_path = data_root.join("state/stop.json");
        let owned_api = TestHealthServer::start(Some(stop_path.clone()));
        let foreign_api = TestHealthServer::start(None);
        let controller = std::sync::Arc::new(LifecycleController::new(
            Some(test_lifecycle_paths(&data_root, &script)),
            owned_api.port,
        ));
        let _close_guard = ShutdownControllerOnDrop(std::sync::Arc::clone(&controller));
        controller.spawn_cold_start();
        wait_for_file(&data_root.join("started.txt"), "owned ready supervisor start");
        let manager_pid = controller.supervisor_pid().expect("owned manager child PID");
        std::fs::write(data_root.join("go.txt"), "start owned descendant")
            .expect("release owned service tree");
        let owned_child = wait_for_child_pid(&data_root.join("child.pid"));
        assert_supervisor_job_contains(&controller, manager_pid);
        assert_supervisor_job_contains(&controller, owned_child);
        let runtime_id = "e".repeat(32);
        write_runtime_status(&data_root, &runtime_id, manager_pid, "starting");
        wait_until(
            || controller.owned_supervisor_alive(),
            "fresh manager identity adoption",
        );
        write_runtime_status(&data_root, &runtime_id, manager_pid, "ready");
        wait_until(
            || controller.state() == LifecycleState::Ready,
            "owned API readiness",
        );
        assert_eq!(
            poll_api_ready(owned_api.port, std::time::Duration::from_secs(2)),
            Readiness::Ready
        );
        assert_eq!(
            poll_api_ready(foreign_api.port, std::time::Duration::from_secs(2)),
            Readiness::Ready
        );

        assert!(controller.shutdown());
        let stop_request: serde_json::Value = serde_json::from_slice(
            &std::fs::read(&stop_path).expect("identity-scoped stop request"),
        )
        .expect("valid stop request JSON");
        assert_eq!(
            stop_request.get("runtimeId").and_then(serde_json::Value::as_str),
            Some(runtime_id.as_str())
        );
        assert!(
            stop_path.exists(),
            "the owned manager receives its identity-scoped stop request"
        );
        assert_process_exited(manager_pid, &data_root, "cmd.exe");
        assert_process_exited(owned_child, &data_root, "powershell.exe");
        wait_until(
            || poll_api_ready(owned_api.port, std::time::Duration::from_millis(100))
                != Readiness::Ready,
            "owned listener shutdown",
        );
        assert_eq!(
            poll_api_ready(foreign_api.port, std::time::Duration::from_secs(2)),
            Readiness::Ready,
            "stopping the owned tree must not stop a separate listener"
        );

        owned_api.stop();
        foreign_api.stop();
        let _ = std::fs::remove_dir_all(&data_root);
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
    fn create_card_escapes_user_supplied_placeholder() {
        // The placeholder is the one host-selected value that could carry HTML
        // metacharacters into the surface; the escaper is the single gate.
        let escaped = escape_html("a\"b<c>&d'e");
        assert_eq!(escaped, "a&quot;b&lt;c&gt;&amp;d&#39;e");
    }

    #[test]
    fn refusal_is_a_finite_code_never_raw_launcher_output() {
        let view = ManagementView {
            first_run: true,
            refusal: Some("PROVISION_TIMEOUT".to_string()),
            workspace: WorkspaceRecord::Absent,
            ..test_view(LifecycleState::Failed, None, None, false, false)
        };
        let html = render_workspace_management(&view);
        assert!(html.contains("PROVISION_TIMEOUT"));
        assert!(!html.contains("Projecta Local:"));
        assert!(!html.contains("<script"));
        assert!(!html.contains("Traceback"));
        assert!(!html.to_lowercase().contains("secret"));
        assert!(!html.contains("managerPid"));
        assert!(!html.contains("dpapi"));
    }

    #[test]
    fn first_run_detection_reads_existing_workspace_only() {
        let data_root = disposable_root("s15-04-first-run-detect");
        std::fs::create_dir_all(data_root.join("config")).expect("config dir");
        let paths = || LifecyclePaths {
            supervisor_exe: std::path::PathBuf::from("C:/nonexistent/ProjectaLocal.exe"),
            local_app_data: std::path::PathBuf::from("C:/nonexistent/localappdata"),
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
        let controller = std::sync::Arc::new(LifecycleController::new(None, DEFAULT_API_PORT));
        assert!(!controller.is_first_run());
        assert!(controller.begin_provision("Any Name").is_err());
        assert_eq!(
            controller.failure_code().as_deref(),
            Some("RUNTIME_PACKAGE_MISSING")
        );
        // Still no supervisor child and no accepted create: nothing to stop.
        assert!(!controller.has_supervisor());
        assert!(!controller.provision_in_flight());
        assert!(controller.shutdown());
    }

    #[test]
    fn provisioning_refuses_an_invalid_name_before_spawning_anything() {
        let data_root = disposable_root("s15-04-invalid-name");
        let controller = std::sync::Arc::new(LifecycleController::new(
            Some(nonexistent_paths(&data_root)),
            DEFAULT_API_PORT,
        ));
        assert!(controller.is_first_run());
        // An invalid name is refused in-process (and synchronously, on the
        // surface's own entry), so the (nonexistent) launcher is never invoked
        // and no workspace config can be written.
        let refused = controller.begin_provision("bad\nname");
        assert_eq!(refused.err().as_deref(), Some("WORKSPACE_NAME_INVALID"));
        assert!(!data_root.join("config/local-runtime.json").is_file());
        assert!(!controller.has_supervisor());
        assert!(!controller.provision_in_flight());
        assert_eq!(controller.state(), LifecycleState::Bootstrap);
        let _ = std::fs::remove_dir_all(&data_root);
    }

    #[cfg(windows)]
    #[test]
    fn closing_during_creation_cancels_the_owned_child() {
        // The close path stops exactly the owned `provision` child: a creation
        // in flight must not outlive the window, and it must not be reported as
        // a success either. `cmd.exe` running a batch that sleeps stands in for
        // the launcher so the test controls the duration; nothing is written.
        let data_root = disposable_root("s15-07-ux-provision-cancel");
        let _root_cleanup = TempRootCleanup(data_root.clone());
        std::fs::create_dir_all(&data_root).expect("data root");
        let script = data_root.join("slow.cmd");
        std::fs::write(&script, b"@ping -n 10 127.0.0.1 >nul\r\n").expect("write script");
        // `spawn_provision` invokes the packaged supervisor with CLI arguments.
        // This direct batch-file path ignores them and sleeps long enough for
        // the test to exercise cancellation without a real launcher.
        let paths = LifecyclePaths {
            supervisor_exe: script,
            local_app_data: data_root.clone(),
            data_root: data_root.clone(),
        };
        let controller =
            std::sync::Arc::new(LifecycleController::new(Some(paths), DEFAULT_API_PORT));
        let _close_guard = ShutdownControllerOnDrop(std::sync::Arc::clone(&controller));
        assert!(controller.is_first_run());
        controller
            .begin_provision("Team Notes")
            .expect("create request accepted");
        // The surface renders the creating overlay from this very state: the
        // accepted request is marked in flight synchronously, before the child
        // registers, so the window never sits on a blocking request.
        let view = controller.management_view();
        assert_eq!(view.state, LifecycleState::Starting);
        assert!(view.provision_pending);
        assert_eq!(view.overlay(), Some(OverlayMode::Creating));
        assert!(render_workspace_management(&view).contains("data-overlay-mode=\"creating\""));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(30);
        while !controller.is_provisioning() && std::time::Instant::now() < deadline {
            std::thread::sleep(std::time::Duration::from_millis(50));
        }
        assert!(
            controller.is_provisioning(),
            "creation must register its owned child"
        );
        // This is the actual window-close entry point: it owns the cancellation
        // and joins both the child and the in-flight creator before returning.
        assert!(controller.shutdown());
        // The create worker returns after the cancel and clears the in-flight
        // marker, so no worker - and therefore no child it could still spawn -
        // outlives the window.
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(30);
        while controller.provision_in_flight() && std::time::Instant::now() < deadline {
            std::thread::sleep(std::time::Duration::from_millis(50));
        }
        assert!(
            !controller.provision_in_flight(),
            "the create worker must finish during close"
        );
        assert!(!controller.is_provisioning());
        assert_eq!(controller.state(), LifecycleState::Stopped);
        // The cancelled action dismisses the overlay: the create card is the
        // reachable surface again, with no false progress and no false success.
        let view = controller.management_view();
        assert_eq!(view.overlay(), None);
        assert!(view.first_run);
        // The stand-in child wrote nothing. For the real launcher the safe
        // interruption boundary is per-file atomicity (`atomic_write`: temp file
        // + fsync + `os.replace`) plus its own refuse-to-overwrite rule, so a
        // cancelled creation can leave a complete record or no record - never a
        // partial or invalid one. This app deletes nothing and never recreates a
        // record; the next launch simply reads what is there.
        assert!(!data_root.join("config/local-runtime.json").is_file());
        // The data root is still an unprovisioned one: the user keeps an
        // explicit, non-silent decision to try again.
        assert!(controller.is_first_run());
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
        let controller = std::sync::Arc::new(LifecycleController::new(
            Some(nonexistent_paths(&data_root)),
            DEFAULT_API_PORT,
        ));
        assert!(!controller.is_first_run());
        let refused = controller.begin_provision("Replacement Name");
        assert_eq!(
            refused.err().as_deref(),
            Some("WORKSPACE_ALREADY_PROVISIONED")
        );
        assert!(!controller.provision_in_flight());
        let preserved =
            std::fs::read_to_string(data_root.join("config/local-runtime.json"))
                .expect("read registry");
        assert_eq!(preserved, "{\"formatVersion\":1}");
        assert!(!controller.has_supervisor());
        let _ = std::fs::remove_dir_all(&data_root);
    }

    /// Paths bound to nonexistent executables, so a provisioning call that is
    /// expected to fail must fail for the code under test, not a spawn reason.
    #[cfg(windows)]
    fn prepare_runtime_root(root: &std::path::Path) {
        std::fs::create_dir_all(root.join("config")).expect("config directory");
        std::fs::create_dir_all(root.join("state")).expect("state directory");
        std::fs::write(
            root.join("config/local-runtime.json"),
            r#"{"formatVersion":1}"#,
        )
        .expect("existing workspace record");
    }

    #[cfg(windows)]
    fn write_runtime_status(
        root: &std::path::Path,
        runtime_id: &str,
        manager_pid: u32,
        state: &str,
    ) {
        std::fs::write(
            root.join("state/runtime.json"),
            serde_json::json!({
                "formatVersion": 1,
                "runtimeId": runtime_id,
                "managerPid": manager_pid,
                "state": state,
            })
            .to_string(),
        )
        .expect("write test runtime status");
    }

    #[cfg(windows)]
    fn test_lifecycle_paths(root: &std::path::Path, script: &std::path::Path) -> LifecyclePaths {
        LifecyclePaths {
            supervisor_exe: script.to_path_buf(),
            local_app_data: root.to_path_buf(),
            data_root: root.to_path_buf(),
        }
    }

    #[cfg(windows)]
    fn write_supervisor_test_script(root: &std::path::Path) -> std::path::PathBuf {
        let script = root.join("supervisor.cmd");
        let started = root.join("started.txt").display().to_string();
        let go = root.join("go.txt").display().to_string();
        let refuse = root.join("refuse.txt").display().to_string();
        let stop_file = root.join("state/stop.json").display().to_string();
        let child_pid = root.join("child.pid").display().to_string();
        std::fs::write(
            &script,
            format!(
                "@echo off\r\n\
                 setlocal\r\n\
                 >\"{started}\" echo started\r\n\
                 :wait_for_go\r\n\
                 if not exist \"{go}\" goto wait_for_go\r\n\
                 powershell.exe -NoProfile -Command \"$PID | Set-Content -NoNewline -Encoding ascii -LiteralPath '{child_pid}'; while ((-not (Test-Path -LiteralPath '{stop_file}')) -and (-not (Test-Path -LiteralPath '{refuse}'))) {{ Start-Sleep -Milliseconds 100 }}; if (Test-Path -LiteralPath '{refuse}') {{ [Console]::Error.WriteLine('Projecta Local: already running [RUNTIME_ALREADY_ACTIVE]'); exit 1 }}\"\r\n\
                 exit /b %errorlevel%\r\n"
            ),
        )
        .expect("write process fixture");
        script
    }

    #[cfg(windows)]
    fn open_exclusive_test_lock(path: &std::path::Path) -> std::fs::File {
        use std::os::windows::fs::OpenOptionsExt as _;
        use std::io::Write as _;
        let mut file = std::fs::OpenOptions::new()
            .create(true)
            .truncate(true)
            .read(true)
            .write(true)
            .share_mode(0)
            .open(path)
            .expect("open exclusive first-runtime lock");
        file.write_all(b"first-runtime-lock sentinel\n")
            .expect("write lock sentinel");
        file.sync_all().expect("flush lock sentinel");
        file
    }
    #[cfg(windows)]
    fn assert_supervisor_job_contains(controller: &LifecycleController, pid: u32) {
        let guard = controller
            .supervisor
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        let supervisor = guard.as_ref().expect("owned supervisor exists");
        assert_eq!(
            supervisor._job.contains_process(pid),
            super::JobMembership::InJob(true),
            "PID {pid} must be a member of this supervisor's kill-on-close job"
        );
    }
    #[cfg(windows)]
    struct ShutdownControllerOnDrop(std::sync::Arc<LifecycleController>);

    #[cfg(windows)]
    impl Drop for ShutdownControllerOnDrop {
        fn drop(&mut self) {
            let _ = self.0.shutdown();
        }
    }
    #[cfg(windows)]
    struct TaskChildCleanup(std::process::Child);

    #[cfg(windows)]
    impl Drop for TaskChildCleanup {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }
    #[cfg(windows)]
    fn assert_test_lock_held(path: &std::path::Path) {
        assert!(
            std::fs::OpenOptions::new().read(true).write(true).open(path).is_err(),
            "the first runtime's exclusive lock handle must remain held"
        );
    }

    #[cfg(windows)]
    fn read_test_lock(file: &mut std::fs::File) -> Vec<u8> {
        use std::io::{Read as _, Seek as _};
        file.seek(std::io::SeekFrom::Start(0)).expect("rewind lock");
        let mut bytes = Vec::new();
        file.read_to_end(&mut bytes).expect("read lock sentinel");
        bytes
    }

    #[cfg(windows)]
    fn wait_for_file(path: &std::path::Path, label: &str) {
        wait_until(|| path.is_file(), label);
    }

    #[cfg(windows)]
    fn wait_until(mut condition: impl FnMut() -> bool, label: &str) {
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(30);
        while std::time::Instant::now() < deadline {
            if condition() {
                return;
            }
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
        assert!(condition(), "timed out waiting for {label}");
    }

    #[cfg(windows)]
    fn wait_for_child_pid(path: &std::path::Path) -> u32 {
        wait_until(
            || {
                std::fs::read_to_string(path)
                    .ok()
                    .and_then(|value| value.trim().parse::<u32>().ok())
                    .is_some()
            },
            "owned child process PID",
        );
        std::fs::read_to_string(path)
            .expect("read child PID")
            .trim()
            .parse()
            .expect("parse child PID")
    }

    #[cfg(windows)]
    fn assert_process_exited(pid: u32, root: &std::path::Path, name: &str) {
        wait_until(
            || fixture_process_matches(pid, root, name) == Some(false),
            "owned process exit by exact fixture command line",
        );
    }


    #[cfg(windows)]
    fn closed_loopback_port() -> u16 {
        let listener =
            std::net::TcpListener::bind("127.0.0.1:0").expect("allocate isolated loopback port");
        listener.local_addr().expect("loopback address").port()
    }

    #[cfg(windows)]
    struct TestHealthServer {
        port: u16,
        stopped: std::sync::Arc<std::sync::atomic::AtomicBool>,
        accept_error: std::sync::Arc<std::sync::Mutex<Option<String>>>,
        thread: Option<std::thread::JoinHandle<()>>,
    }

    #[cfg(windows)]
    impl TestHealthServer {
        fn start(stop_file: Option<std::path::PathBuf>) -> Self {
            use std::io::{Read as _, Write as _};
            use std::net::TcpListener;
            use std::sync::atomic::{AtomicBool, Ordering};
            use std::sync::Arc;
            let listener = TcpListener::bind("127.0.0.1:0").expect("bind test health listener");
            listener
                .set_nonblocking(true)
                .expect("nonblocking test health listener");
            let port = listener.local_addr().expect("health listener address").port();
            let stopped = Arc::new(AtomicBool::new(false));
            let thread_stopped = Arc::clone(&stopped);
            let accept_error = Arc::new(std::sync::Mutex::new(None));
            let thread_accept_error = Arc::clone(&accept_error);
            let thread = std::thread::spawn(move || {
                while !thread_stopped.load(Ordering::Relaxed)
                    && !stop_file.as_ref().is_some_and(|path| path.is_file())
                {
                    match listener.accept() {
                        Ok((mut stream, _)) => {
                            let mut request = [0_u8; 1024];
                            let _ = stream.read(&mut request);
                            let body =
                                "{\"status\":\"ready\",\"semanticCore\":\"ready\",\"oidc\":\"ready\"}";
                            let response = format!(
                                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                                body.len()
                            );
                            let _ = stream.write_all(response.as_bytes());
                        }
                        Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                            std::thread::sleep(std::time::Duration::from_millis(10));
                        }
                        Err(error) => {
                            *thread_accept_error
                                .lock()
                                .unwrap_or_else(|poisoned| poisoned.into_inner()) =
                                Some(error.to_string());
                            break;
                        }
                    }
                }
            });
            Self {
                port,
                stopped,
                accept_error,
                thread: Some(thread),
            }
        }

        fn stop(mut self) {
            use std::sync::atomic::Ordering;
            self.stopped.store(true, Ordering::Relaxed);
            if let Some(thread) = self.thread.take() {
                thread.join().expect("join health listener");
            }
        }
    }
    #[cfg(windows)]
    impl Drop for TestHealthServer {
        fn drop(&mut self) {
            use std::sync::atomic::Ordering;
            self.stopped.store(true, Ordering::Relaxed);
            if let Some(thread) = self.thread.take() {
                let _ = thread.join();
            }
        }
    }

    fn nonexistent_paths(data_root: &std::path::Path) -> LifecyclePaths {
        LifecyclePaths {
            supervisor_exe: std::path::PathBuf::from("C:/nonexistent/ProjectaLocal.exe"),
            local_app_data: data_root.to_path_buf(),
            data_root: data_root.to_path_buf(),
        }
    }

    #[cfg(windows)]
    struct TempRootCleanup(std::path::PathBuf);

    #[cfg(windows)]
    impl Drop for TempRootCleanup {
        fn drop(&mut self) {
            let _ = std::fs::write(self.0.join("refuse.txt"), "fixture cleanup");
            let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
            loop {
                match fixture_child_process_ids(&self.0) {
                    Some(pids) if pids.is_empty() => break,
                    Some(pids) if std::time::Instant::now() >= deadline => {
                        for pid in pids {
                            terminate_fixture_child_if_owned(pid, &self.0);
                        }
                        break;
                    }
                    Some(_) => std::thread::sleep(std::time::Duration::from_millis(100)),
                    None => {
                        eprintln!(
                            "could not validate fixture child identities under {}",
                            self.0.display()
                        );
                        return;
                    }
                }
            }
            if fixture_child_process_ids(&self.0).is_some_and(|pids| pids.is_empty()) {
                let _ = std::fs::remove_dir_all(&self.0);
            } else {
                eprintln!(
                    "fixture root retained because an exact child identity remains under {}",
                    self.0.display()
                );
            }
        }
    }

    #[cfg(windows)]
    fn fixture_child_process_ids(root: &std::path::Path) -> Option<Vec<u32>> {
        let root = root.to_string_lossy().replace('\'', "''");
        let command = format!(
            "$ErrorActionPreference='Stop'; try {{ Get-CimInstance Win32_Process -Filter \"Name = 'powershell.exe'\" | Where-Object {{ $_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine.Contains('{root}') }} | ForEach-Object {{ $_.ProcessId }} }} catch {{ exit 2 }}"
        );
        let output = std::process::Command::new("powershell.exe")
            .args(["-NoProfile", "-NonInteractive", "-Command"])
            .arg(command)
            .output()
            .ok()?;
        if !output.status.success() {
            return None;
        }
        String::from_utf8(output.stdout)
            .ok()?
            .lines()
            .map(|line| line.trim().parse().ok())
            .collect()
    }

    #[cfg(windows)]
    fn fixture_child_matches(pid: u32, root: &std::path::Path) -> Option<bool> {
        fixture_process_matches(pid, root, "powershell.exe")
    }

    #[cfg(windows)]
    fn fixture_process_matches(
        pid: u32,
        root: &std::path::Path,
        expected_name: &str,
    ) -> Option<bool> {
        let root = root.to_string_lossy().replace('\'', "''");
        let expected_name = expected_name.replace('\'', "''");
        let command = format!(
            "$ErrorActionPreference='Stop'; try {{ $process = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; if ($process -and $process.ProcessId -ne $PID -and $process.Name -ieq '{expected_name}' -and $process.CommandLine -and $process.CommandLine.Contains('{root}')) {{ Write-Output 'OWNED' }} else {{ Write-Output 'OTHER' }} }} catch {{ exit 2 }}"
        );
        let output = std::process::Command::new("powershell.exe")
            .args(["-NoProfile", "-NonInteractive", "-Command"])
            .arg(command)
            .output()
            .ok()?;
        if !output.status.success() {
            return None;
        }
        let result = String::from_utf8(output.stdout).ok()?;
        match result.trim() {
            "OWNED" => Some(true),
            "OTHER" => Some(false),
            _ => None,
        }
    }

    #[cfg(windows)]
    fn terminate_fixture_child_if_owned(pid: u32, root: &std::path::Path) {
        const PROCESS_TERMINATE: u32 = 0x0001;
        const PROCESS_QUERY_LIMITED_INFORMATION: u32 = 0x1000;
        let process = unsafe {
            super::OpenProcess(
                PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION,
                0,
                pid,
            )
        };
        if process == 0 {
            return;
        }
        if fixture_child_matches(pid, root) == Some(true) {
            unsafe {
                super::TerminateProcess(process, 1);
            }
        }
        unsafe {
            super::CloseHandle(process);
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
    #[test]
    fn theme_mode_default_and_parsing() {
        assert_eq!(ThemeMode::default(), ThemeMode::System);
        assert_eq!(ThemeMode::from_str_loose("light"), Some(ThemeMode::Light));
        assert_eq!(ThemeMode::from_str_loose("DARK"), Some(ThemeMode::Dark));
        assert_eq!(ThemeMode::from_str_loose(" system "), Some(ThemeMode::System));
        assert_eq!(ThemeMode::from_str_loose("other"), None);

        let prefs = UiPreferences { theme_mode: ThemeMode::Dark };
        let serialized = serde_json::to_string(&prefs).expect("serialize");
        assert!(serialized.contains("\"themeMode\":\"dark\""));

        let deserialized: UiPreferences = serde_json::from_str(&serialized).expect("deserialize");
        assert_eq!(deserialized.theme_mode, ThemeMode::Dark);

        // Fallback default for missing fields
        let empty: UiPreferences = serde_json::from_str("{}").expect("deserialize empty");
        assert_eq!(empty.theme_mode, ThemeMode::System);
    }

    #[test]
    fn ui_preferences_persistence_and_fallback() {
        let root = disposable_root("s15-07-theme-prefs");
        let paths = LifecyclePaths {
            supervisor_exe: std::path::PathBuf::from("C:/nonexistent/ProjectaLocal.exe"),
            local_app_data: root.clone(),
            data_root: root.clone(),
        };

        // Absent file returns default
        assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::System);

        // Write dark
        let prefs = UiPreferences { theme_mode: ThemeMode::Dark };
        paths.write_ui_preferences(&prefs).expect("write preferences");
        assert!(paths.preferences_config_path().is_file());
        assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::Dark);

        // Controller loads and updates
        let controller = LifecycleController::new(Some(paths.clone()), DEFAULT_API_PORT);
        assert_eq!(controller.theme_mode(), ThemeMode::Dark);
        controller.set_theme_mode(ThemeMode::Light).expect("set light");
        assert_eq!(controller.theme_mode(), ThemeMode::Light);
        assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::Light);

        // Corrupted JSON falls back safely
        std::fs::write(paths.preferences_config_path(), "{ invalid json").expect("corrupt");
        assert_eq!(paths.read_ui_preferences().theme_mode, ThemeMode::System);

        let _ = std::fs::remove_dir_all(&root);
    }

}
