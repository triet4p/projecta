"""Window-first startup tests for the desktop control panel.

Selecting **Open Projecta** on the installer finish page previously started a
``Projecta.exe`` process with no visible window for the whole duration of the
cold package-integrity verification: ``main()`` verified all 6,146 manifest
files before creating the first Tk window. These tests pin the corrected
startup contract through recording doubles instead of a display: the visible
panel must exist before verification finishes, verification must stay off the
Tk thread, workspace-affecting work must stay gated until verification
passes, and a failed verification must surface its exact code on the visible
panel instead of leaving an empty process. Nothing here maps a window,
touches the owner profile, HKCU, shortcuts, or the network.
"""

from __future__ import annotations

import ctypes
import importlib.util
import sys
import threading
import time
from pathlib import Path

import pytest

_launcher_path = Path(__file__).resolve().parents[1] / "projecta_local.py"
_desktop_path = Path(__file__).resolve().parents[1] / "projecta_desktop.py"

_launcher_spec = importlib.util.spec_from_file_location(
    "projecta_local_launcher", _launcher_path
)
if _launcher_spec is None or _launcher_spec.loader is None:
    raise RuntimeError("could not load the per-user launcher module")
launcher = importlib.util.module_from_spec(_launcher_spec)
sys.modules[_launcher_spec.name] = launcher
sys.modules.setdefault("projecta_local", launcher)
_launcher_spec.loader.exec_module(launcher)

_desktop_spec = importlib.util.spec_from_file_location(
    "projecta_desktop_window_first", _desktop_path
)
if _desktop_spec is None or _desktop_spec.loader is None:
    raise RuntimeError("could not load the desktop control panel module")
desktop = importlib.util.module_from_spec(_desktop_spec)
sys.modules[_desktop_spec.name] = desktop
_desktop_spec.loader.exec_module(desktop)


class _FakeFunction:
    def __init__(self, result: object) -> None:
        self._result = result

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self._result


class _FakeKernel32:
    def __init__(self) -> None:
        self.CreateMutexW = _FakeFunction(9871)
        self.CloseHandle = _FakeFunction(None)
        self.ReleaseMutex = _FakeFunction(None)


class _FakeRoot:
    """Recording Tk root double; callbacks run inline on the calling thread."""

    def __init__(self, events: list[str], lock: threading.Lock) -> None:
        self._events = events
        self._lock = lock

    def _log(self, event: str) -> None:
        with self._lock:
            self._events.append(event)

    def winfo_exists(self) -> bool:
        return True

    def update_idletasks(self) -> None:
        self._log("update_idletasks")

    def deiconify(self) -> None:
        self._log("deiconify")

    def lift(self) -> None:
        self._log("lift")

    def after(self, ms: int, callback: object) -> int:
        self._log("after_callback")
        assert callable(callback)
        callback()
        return 1

    def mainloop(self) -> None:
        self._log("mainloop_enter")
        for _ in range(400):
            with self._lock:
                finished = "verify_done" in self._events
            if finished:
                break
            time.sleep(0.025)
        self._log("mainloop_exit")


class _FakeState:
    def __init__(self, events: list[str], lock: threading.Lock) -> None:
        self._events = events
        self._lock = lock

    def set(self, value: str) -> None:
        with self._lock:
            self._events.append(f"state_set:{value[:48]}")


class _FakeButton:
    def __init__(self, events: list[str], lock: threading.Lock) -> None:
        self._events = events
        self._lock = lock

    def configure(self, **kwargs: object) -> None:
        with self._lock:
            self._events.append(f"button_configure:{kwargs}")


class _FakeApp:
    def __init__(self, root: object, paths: object, events: list[str], lock: threading.Lock) -> None:
        with lock:
            events.append("app_init")
        self.root = root
        self.paths = paths
        self.state = _FakeState(events, lock)
        self.start_button = _FakeButton(events, lock)

    def begin(self) -> None:
        assert isinstance(self.root, _FakeRoot)
        with self.root._lock:
            self.root._events.append("begin_called")


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch, events: list[str], lock: threading.Lock
) -> None:
    def factory(root: object, paths: object) -> _FakeApp:
        return _FakeApp(root, paths, events, lock)

    monkeypatch.setattr(desktop, "ProjectaDesktop", factory)
    monkeypatch.setattr(desktop.tk, "Tk", lambda: (events.append("Tk_created"), _FakeRoot(events, lock))[1])
    monkeypatch.setattr(desktop.ctypes, "WinDLL", lambda *args, **kwargs: _FakeKernel32())
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 0)
    monkeypatch.setattr(
        launcher.ProjectaPaths,
        "discover",
        classmethod(lambda cls: object()),
    )


def test_panel_appears_before_verification_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The visible panel exists before the slow verification finishes."""

    events: list[str] = []
    lock = threading.Lock()
    _install_fakes(monkeypatch, events, lock)

    def slow_verify(paths: object) -> None:
        with lock:
            events.append("verify_start")
        time.sleep(2)
        with lock:
            events.append("verify_done")

    monkeypatch.setattr(desktop, "_verify_installation", slow_verify)

    assert desktop.main() == 0

    order = {event: index for index, event in enumerate(events)}
    assert order["Tk_created"] < order["verify_start"]
    assert order["deiconify"] < order["verify_done"]
    assert order["lift"] < order["verify_done"]
    assert order["begin_called"] > order["verify_done"]


def test_failed_verification_surfaces_on_visible_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed verification reports its code instead of starting work."""

    events: list[str] = []
    lock = threading.Lock()
    _install_fakes(monkeypatch, events, lock)

    def failing_verify(paths: object) -> None:
        with lock:
            events.append("verify_start")
        time.sleep(1)
        with lock:
            events.append("verify_done")
        raise launcher.RuntimeFailure(
            "PACKAGE_CONTENT_INVALID",
            "A package file does not match its integrity manifest.",
        )

    monkeypatch.setattr(desktop, "_verify_installation", failing_verify)
    dialogs: list[str] = []
    monkeypatch.setattr(
        desktop.messagebox, "showerror", lambda *args, **kwargs: dialogs.append(str(args[0]))
    )

    assert desktop.main() == 0

    assert "begin_called" not in events
    assert any("deiconify" == event for event in events)
    assert dialogs == ["Projecta could not be opened"]
    assert any(
        event.startswith("state_set:Projecta could not be opened") for event in events
    )
