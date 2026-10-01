"""Windows control panel for the bundled Projecta 0.7.0 local runtime."""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import projecta_local as launcher

BROWSER_URL = f"http://127.0.0.1:{launcher.PORTS['api']}/"
SERVICE_NAMES = {
    "postgres": "PostgreSQL",
    "fuseki": "Fuseki / TDB2",
    "semanticCore": "Semantic Core",
    "api": "Projecta API",
}


class ProjectaDesktop:
    """Present service status and normal start, stop, browser, and log actions."""

    def __init__(self, root: tk.Tk, paths: launcher.ProjectaPaths) -> None:
        self.root = root
        self.paths = paths
        self.manager_process: subprocess.Popen[bytes] | None = None
        self.state = tk.StringVar(value="Checking installation…")
        self.service_states = {
            name: tk.StringVar(value="Not started") for name in SERVICE_NAMES
        }
        self.start_button: ttk.Button
        self.stop_button: ttk.Button
        self.browser_button: ttk.Button

        root.title("Projecta 0.7.0 — unsigned test pre-release")
        root.geometry("620x490")
        root.minsize(540, 430)
        root.protocol("WM_DELETE_WINDOW", self._close)

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Projecta 0.7.0", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "UNSIGNED TEST PRE-RELEASE — Windows cannot verify the publisher. "
                "Check the owner's installer SHA-256 before running it. "
                "This does not pass the signed or clean-install release gate."
            ),
            foreground="#8b2f00",
            wraplength=570,
            justify="left",
        ).pack(anchor="w", pady=(8, 16))

        ttk.Label(frame, textvariable=self.state, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        services = ttk.LabelFrame(frame, text="Local services", padding=12)
        services.pack(fill="x", pady=(12, 12))
        for row, (name, label) in enumerate(SERVICE_NAMES.items()):
            ttk.Label(services, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Label(services, textvariable=self.service_states[name]).grid(
                row=row, column=1, sticky="e", padx=(30, 0), pady=3
            )
        services.columnconfigure(0, weight=1)

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(2, 10))
        self.start_button = ttk.Button(actions, text="Start Projecta", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="Stop services", command=self.stop)
        self.stop_button.pack(side="left", padx=(8, 0))
        self.browser_button = ttk.Button(
            actions, text="Open Projecta in browser", command=self.open_browser, state="disabled"
        )
        self.browser_button.pack(side="left", padx=(8, 0))

        tools = ttk.Frame(frame)
        tools.pack(fill="x", pady=(0, 12))
        ttk.Button(tools, text="Open safe diagnostics folder", command=self.open_logs).pack(side="left")
        ttk.Button(tools, text="Exit", command=self._close).pack(side="right")

        ttk.Label(
            frame,
            text=f"Mutable data: {self.paths.data_root}\nLogs: {self.paths.log_file}",
            wraplength=570,
            justify="left",
        ).pack(anchor="w", side="bottom")

    def begin(self) -> None:
        if not self.paths.installation_config.is_file() or not self.paths.local_config.is_file():
            self.root.after(150, self._first_run)
            return
        self.root.after(150, self.start)
        self.root.after(1000, self.refresh)

    def _first_run(self) -> None:
        name = simpledialog.askstring(
            "Create your workspace",
            "Choose a display name for this local Projecta workspace:",
            initialvalue="My Projecta Workspace",
            parent=self.root,
        )
        if name is None:
            self.root.destroy()
            return
        if not name.strip() or len(name.strip()) > 128 or any(ord(char) < 32 for char in name):
            messagebox.showerror(
                "Workspace name not accepted",
                "Enter a non-empty name of at most 128 characters.",
                parent=self.root,
            )
            self.root.after(150, self._first_run)
            return
        self.state.set("Creating your workspace and protecting local secrets…")
        self.start_button.configure(state="disabled")
        executable = self.paths.package_root / "ProjectaLocal.exe"

        def provision() -> None:
            try:
                result = subprocess.run(
                    [str(executable), "install", "--workspace-name", name.strip()],
                    cwd=self.paths.package_root,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=180,
                )
                detail = result.stderr.decode("utf-8", errors="replace").strip()
                success = result.returncode == 0
                if success:
                    detail = result.stdout.decode("utf-8", errors="replace").strip()
            except (OSError, subprocess.TimeoutExpired) as error:
                success = False
                detail = str(error)
            try:
                self.root.after(0, lambda: self._finish_first_run(success, detail))
            except tk.TclError:
                pass

        threading.Thread(target=provision, name="projecta-first-run-provision", daemon=True).start()


    def _finish_first_run(self, success: bool, detail: str) -> None:
        if not self.root.winfo_exists():
            return
        self.start_button.configure(state="normal")
        if not success:
            self.state.set("First-run setup failed. Local data was retained.")
            messagebox.showerror(
                "Projecta setup failed",
                detail or "Projecta could not finish its first-run setup. Open the diagnostics folder for details.",
                parent=self.root,
            )
            return
        self.state.set("Workspace ready. Starting Projecta…")
        self.start()

    def start(self) -> None:
        try:
            if not self.paths.installation_config.is_file() or not self.paths.local_config.is_file():
                self._first_run()
                return
            if launcher.runtime_is_active(self.paths):
                self.refresh()
                self.open_browser()
                return
            if self.manager_process is not None and self.manager_process.poll() is None:
                self.state.set("Starting Projecta services…")
                self.root.after(1000, self.refresh)
                return
            executable = self.paths.package_root / "ProjectaLocal.exe"
            self.manager_process = subprocess.Popen(
                [str(executable), "start"],
                cwd=self.paths.package_root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.state.set("Starting PostgreSQL, Fuseki, Semantic Core, and API…")
            self.start_button.configure(state="disabled")
            self.root.after(1000, self.refresh)
        except launcher.RuntimeFailure as error:
            self.state.set(f"Projecta could not start ({error.code}).")
            messagebox.showerror("Projecta could not start", error.message, parent=self.root)
        except OSError:
            self.state.set("Projecta could not start. Open diagnostics for details.")
            messagebox.showerror(
                "Projecta could not start",
                "The bundled launcher could not be started. Local data was retained.",
                parent=self.root,
            )

    def stop(self) -> None:
        try:
            launcher.request_stop(self.paths)
            self.state.set("Stopping services safely. Local data is retained…")
            self.root.after(1000, self.refresh)
        except launcher.RuntimeFailure as error:
            self.state.set(f"Projecta could not stop ({error.code}).")
            messagebox.showerror("Projecta could not stop", error.message, parent=self.root)

    def open_browser(self) -> None:
        if not launcher.runtime_is_active(self.paths):
            self.state.set("Projecta is not ready yet. Wait for all services to report ready.")
            return
        if not webbrowser.open(BROWSER_URL, new=2):
            messagebox.showinfo(
                "Projecta is ready",
                f"Open this local address in your browser:\n{BROWSER_URL}",
                parent=self.root,
            )

    def open_logs(self) -> None:
        try:
            self.paths.log_file.parent.mkdir(parents=True, exist_ok=True)
            os.startfile(str(self.paths.log_file.parent))
        except OSError:
            messagebox.showerror(
                "Diagnostics unavailable",
                f"Projecta's safe diagnostic log is stored at:\n{self.paths.log_file}",
                parent=self.root,
            )

    def refresh(self) -> None:
        if not self.root.winfo_exists():
            return
        try:
            active = launcher.runtime_is_active(self.paths)
            status = launcher.load_json(self.paths.status_file, "RUNTIME_STATUS_INVALID")
        except launcher.RuntimeFailure:
            active = False
            status = {"state": "stopped", "services": {}}
        reported_state = status.get("state")
        state = (
            reported_state
            if active or reported_state in {"failed", "shutdown-failed"}
            else "stopped"
        )
        for name in SERVICE_NAMES:
            services = status.get("services")
            value = services.get(name) if isinstance(services, dict) else None
            if not active and state == "stopped":
                value = "stopped"
            self.service_states[name].set(value.capitalize() if isinstance(value, str) else "Stopped")
        if state == "ready":
            self.state.set("Ready — all four local services are running.")
            self.browser_button.configure(state="normal")
            self.start_button.configure(state="normal")
        elif state in {"starting", "stopping", "shutdown-failed"}:
            self.state.set(f"Projecta is {state}. Local data is retained.")
            self.browser_button.configure(state="disabled")
            self.start_button.configure(state="disabled" if state == "starting" else "normal")
        elif state == "failed":
            code = status.get("failureCode")
            self.state.set(f"Startup failed ({code if isinstance(code, str) else 'see diagnostics'}).")
            self.browser_button.configure(state="disabled")
            self.start_button.configure(state="normal")
        else:
            self.state.set("Stopped — local data is retained.")
            self.browser_button.configure(state="disabled")
            self.start_button.configure(state="normal")
        self.root.after(1000, self.refresh)

    def _close(self) -> None:
        if launcher.runtime_is_active(self.paths) and not messagebox.askyesno(
            "Projecta is still running",
            "Keep Projecta's local services running after closing this control panel?\n\n"
            "Choose No to return and stop services first.",
            parent=self.root,
        ):
            return
        self.root.destroy()


def _show_startup_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, "Projecta 0.7.0", 0x10)


def _single_instance_mutex(kernel32: object) -> int:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    identity = hashlib.sha256(local_app_data.casefold().encode("utf-8")).hexdigest()[:16]
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel32.CreateMutexW(None, True, f"Local\\Projecta-0.7.0-{identity}")
    if not handle:
        raise OSError("The Projecta window could not reserve its single-instance lock.")
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return 0
    return int(handle)


def main() -> int:
    if os.name != "nt":
        return 2
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    try:
        mutex = _single_instance_mutex(kernel32)
        if not mutex:
            ctypes.windll.user32.MessageBoxW(
                None, "Projecta is already open for this Windows user.", "Projecta 0.7.0", 0x40
            )
            return 0
        paths = launcher.ProjectaPaths.discover()
        manifest = launcher.load_runtime_manifest(paths)
        launcher._require_package_distribution(manifest)
    except launcher.RuntimeFailure as error:
        _show_startup_error(f"Projecta could not be opened: {error.message} [{error.code}]\n\nLocal data was not deleted.")
        return 2
    except OSError:
        _show_startup_error("Projecta could not reserve its per-user startup lock.")
        return 2

    try:
        root = tk.Tk()
        app = ProjectaDesktop(root, paths)
        app.begin()
        root.mainloop()
    except tk.TclError:
        _show_startup_error("The Projecta control panel could not be opened. Local data was not deleted.")
        return 2
    finally:
        kernel32.ReleaseMutex.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.ReleaseMutex(mutex)
        kernel32.CloseHandle(mutex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
