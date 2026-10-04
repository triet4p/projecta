"""Per-user Windows launcher for the bundled Projecta local runtime."""

from __future__ import annotations

import argparse
import base64
import ctypes
import ctypes.wintypes
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

APP_VERSION = "0.7.0"
DATA_CONTRACT_VERSION = 1
UNSIGNED_PRE_RELEASE_VERSION = "0.7.0"
UNSIGNED_PRE_RELEASE_CHANNEL = "unsigned-pre-release-test"
UNSIGNED_PRE_RELEASE_EXCEPTION = "projecta-0.7.0-unsigned-pre-release-test"

RUNTIME_VERSIONS = {
    "python": "3.12.10",
    "java": "21.0.12.1+1",
    "fuseki": "6.2.0",
    "postgresql": "16.15",
}
VC_RUNTIME_PREREQUISITE = {
    "formatVersion": 1,
    "architecture": "x64",
    "minimumVersion": "14.42.34438.0",
    "sourceUrl": "https://aka.ms/vc14/vc_redist.x64.exe",
    "publisher": "Microsoft Corporation",
    "installerFileName": "VC_redist.x64.exe",
    "integrityContract": "sha256-of-authenticode-verified-download-rechecked-before-launch",
}
VC_RUNTIME_DLL_PATTERN = re.compile(
    r"^(?:msvcp140|msvcr140|vcruntime140|vccorlib140|concrt140|vcomp140|vcamp140|mfc140u?|mfcm140u?)[A-Za-z0-9_]*\.dll$",
    re.IGNORECASE,
)
MSVC_RUNTIME_DLL_PATTERN = re.compile(
    r"^(?:msvcp|msvcr|vcruntime|vccorlib|concrt|vcomp|vcamp|mfc|mfcm|msvcm|atl)[0-9]+[A-Za-z0-9_]*\.dll$",
    re.IGNORECASE,
)

VC_RUNTIME_INSTALLER_PATTERN = re.compile(
    r"^(?:vc_redist|vcredist)(?:[._-][A-Za-z0-9-]+)?\.exe$",
    re.IGNORECASE,
)


def _is_app_local_vc_runtime(path: Path) -> bool:
    return VC_RUNTIME_DLL_PATTERN.fullmatch(path.name) is not None


def _is_msvc_runtime_dll(path: Path) -> bool:
    return MSVC_RUNTIME_DLL_PATTERN.fullmatch(path.name) is not None


def _is_vc_runtime_installer(path: Path) -> bool:
    return VC_RUNTIME_INSTALLER_PATTERN.fullmatch(path.name) is not None



def _validate_vc_runtime_prerequisite(
    package_root: Path,
    manifest: Mapping[str, object],
    *,
    error_code: str,
) -> None:
    if manifest.get("vcRuntimePrerequisite") != VC_RUNTIME_PREREQUISITE:
        raise RuntimeFailure(error_code, "The package Visual C++ prerequisite contract is unsupported.")
    policy_path = package_root / "runtime" / "vc-runtime-policy.json"
    policy = load_json(policy_path, error_code)
    if policy != VC_RUNTIME_PREREQUISITE:
        raise RuntimeFailure(error_code, "The package Visual C++ prerequisite policy is invalid.")


try:
    from _projecta_update_trust import PUBLIC_KEY_B64 as RELEASE_UPDATE_PUBLIC_KEY_B64
except ModuleNotFoundError:
    RELEASE_UPDATE_PUBLIC_KEY_B64 = None

PORTS = {"postgres": 15432, "fuseki": 18303, "semanticCore": 18080, "api": 18732}
HTTP_PROBE_TIMEOUT_SECONDS = 2.0
# Leave one second beyond each nested readiness request: Fuseki uses 3s and the API's Core client uses 3s.
SEMANTIC_CORE_READINESS_TIMEOUT_SECONDS = 4.0
API_READINESS_TIMEOUT_SECONDS = 4.0
READINESS_PROBE_TIMEOUTS = {
    "semanticCore": SEMANTIC_CORE_READINESS_TIMEOUT_SECONDS,
    "api": API_READINESS_TIMEOUT_SECONDS,
}
HEALTH_RESPONSE_BODY_LIMIT = 1024
SNAPSHOT_PATHS = (
    PurePosixPath("data"),
    PurePosixPath("config/local-runtime.json"),
    PurePosixPath("config/installation.json"),
    PurePosixPath("secrets/launcher.dpapi"),
)
BACKUP_ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
ACTOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


class RuntimeFailure(Exception):
    """Sanitized operational error with a stable diagnostic code."""

    def __init__(self, code: str, message: str, service: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.service = service
        self.message = message


@dataclass(frozen=True, slots=True)
class HttpProbeResult:
    status_code: int | None
    response_body: str | None
    failure: str | None
    elapsed_ms: int


class RuntimeAlreadyActive(RuntimeFailure):
    def __init__(self) -> None:
        super().__init__("RUNTIME_ALREADY_ACTIVE", "Projecta Local is already running.")


@dataclass(frozen=True, slots=True)
class ProjectaPaths:
    package_root: Path
    data_root: Path

    @property
    def runtime_manifest(self) -> Path:
        return self.package_root / "runtime-manifest.json"

    @property
    def runtime(self) -> Path:
        return self.package_root / "runtime"

    @property
    def project(self) -> Path:
        return self.package_root / "projecta"

    @property
    def data(self) -> Path:
        return self.data_root / "data"

    @property
    def config(self) -> Path:
        return self.data_root / "config"

    @property
    def local_config(self) -> Path:
        return self.config / "local-runtime.json"

    @property
    def installation_config(self) -> Path:
        return self.config / "installation.json"

    @property
    def protected_secrets(self) -> Path:
        return self.data_root / "secrets" / "launcher.dpapi"

    @property
    def status_file(self) -> Path:
        return self.data_root / "state" / "runtime.json"

    @property
    def stop_file(self) -> Path:
        return self.data_root / "state" / "stop.json"

    @property
    def lock_file(self) -> Path:
        return self.data_root / "state" / "runtime.lock"

    @property
    def log_file(self) -> Path:
        return self.data_root / "logs" / "launcher.log"

    @property
    def backups(self) -> Path:
        return self.data_root / "backups"

    @property
    def recovery(self) -> Path:
        return self.data_root / "recovery"

    @classmethod
    def discover(cls) -> ProjectaPaths:
        override_package = os.environ.get("PROJECTA_LAUNCHER_PACKAGE_ROOT")
        override_data = os.environ.get("PROJECTA_LAUNCHER_DATA_ROOT")
        if not getattr(sys, "frozen", False) and (override_package or override_data):
            if not override_package or not override_data:
                raise RuntimeFailure(
                    "LOCAL_DATA_ROOT_MISSING",
                    "Both launcher package and data root overrides are required for a staged check.",
                )
            return cls(Path(override_package), Path(override_data))
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise RuntimeFailure("LOCAL_DATA_ROOT_MISSING", "Windows did not provide a per-user local data directory.")
        if getattr(sys, "frozen", False):
            package_root = Path(sys.executable).resolve().parent
        else:
            package_root = Path(__file__).resolve().parents[1]
        return cls(package_root, Path(local_app_data) / "Projecta")

    def ensure_user_directories(self) -> None:
        for directory in (
            self.data / "postgres",
            self.data / "fuseki",
            self.data / "sqlite",
            self.data / "evidence",
            self.config,
            self.protected_secrets.parent,
            self.status_file.parent,
            self.log_file.parent,
            self.backups,
            self.recovery,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    project_id: str
    project_name: str
    actor_id: str


@dataclass(frozen=True, slots=True)
class RuntimeSecrets:
    postgres_password: str
    trusted_context_secret: str
    secret_store_master_key: str


@dataclass(slots=True)
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    control_pipe: bool


JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


def _windows_job_for_kill_on_close() -> object | None:
    """Create a Windows Job Object that kills owned children when the manager exits."""
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return None

        class _BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class _ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimits),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        info = _ExtendedLimits()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        JobObjectExtendedLimitInformation = 9
        if not kernel32.SetInformationJobObject(
            handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            kernel32.CloseHandle(handle)
            return None
        return handle
    except OSError:
        return None


def _assign_windows_process_to_job(job: object | None, process: subprocess.Popen[str]) -> bool:
    """Assign one owned child to the manager Job Object; never touches other processes."""
    if os.name != "nt" or job is None:
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = getattr(process, "_handle", None)
        if handle is None:
            return False
        return bool(kernel32.AssignProcessToJobObject(int(job), int(handle)))
    except (OSError, ValueError, TypeError):
        return False


class ProcessHost:
    """Own child process handles in one Job Object; private stdin pipe is the graceful stop."""

    def __init__(self) -> None:
        self.processes: dict[str, ManagedProcess] = {}
        self._job: object | None = _windows_job_for_kill_on_close()
        self._job_assigned: dict[str, bool] = {}

    @property
    def job_handle(self) -> object | None:
        return self._job

    def job_owned(self, name: str) -> bool:
        return bool(self._job_assigned.get(name, False))

    def close_job(self) -> None:
        if os.name == "nt" and self._job is not None:
            try:
                ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(int(self._job))
            except OSError:
                pass
        self._job = None

    def start(
        self,
        name: str,
        command: Sequence[str],
        environment: Mapping[str, str],
        working_directory: Path,
        *,
        control_pipe: bool = True,
    ) -> ManagedProcess:
        if name in self.processes:
            raise RuntimeFailure("PROCESS_OWNERSHIP_CONFLICT", "A service process is already registered.", name)
        creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                list(command),
                cwd=working_directory,
                env=dict(environment),
                stdin=subprocess.PIPE if control_pipe else subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="ascii",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )
        except OSError as error:
            raise RuntimeFailure("SERVICE_LAUNCH_FAILED", "A bundled service could not be started.", name) from error
        child = ManagedProcess(name, process, control_pipe)
        self.processes[name] = child
        self._job_assigned[name] = _assign_windows_process_to_job(self._job, process)
        return child

    def run_task(
        self,
        name: str,
        command: Sequence[str],
        environment: Mapping[str, str],
        working_directory: Path,
        *,
        timeout: float,
        capture_stdout: bool = False,
    ) -> str:
        try:
            result = subprocess.run(
                list(command),
                cwd=working_directory,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="ascii",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeFailure("SERVICE_TASK_TIMEOUT", "A required setup task timed out.", name) from error
        except OSError as error:
            raise RuntimeFailure("SERVICE_TASK_FAILED", "A required setup task could not run.", name) from error
        if result.returncode != 0:
            raise RuntimeFailure("SERVICE_TASK_FAILED", "A required setup task failed; its output was suppressed.", name)
        return result.stdout or ""

    def check_alive(self, name: str) -> None:
        child = self.processes.get(name)
        if child is None or child.process.poll() is not None:
            raise RuntimeFailure("SERVICE_EXITED", "A service exited unexpectedly.", name)

    def stop(self, name: str, timeout: float = 45.0) -> None:
        child = self.processes.get(name)
        if child is None:
            return
        if child.process.poll() is not None:
            if child.process.stdin is not None:
                child.process.stdin.close()
            del self.processes[name]
            return
        if child.control_pipe and child.process.stdin is not None and not child.process.stdin.closed:
            try:
                child.process.stdin.write("stop\n")
                child.process.stdin.flush()
                child.process.stdin.close()
            except (BrokenPipeError, OSError, ValueError) as error:
                raise RuntimeFailure("GRACEFUL_STOP_FAILED", "A service control pipe failed during shutdown.", name) from error
        try:
            return_code = child.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise RuntimeFailure("GRACEFUL_STOP_TIMEOUT", "A service did not stop gracefully; its dependencies remain running.", name) from error
        if child.process.stdin is not None:
            child.process.stdin.close()
        del self.processes[name]
        self._job_assigned.pop(name, None)
        if not self.processes:
            self.close_job()
        if return_code != 0:
            raise RuntimeFailure("GRACEFUL_STOP_FAILED", "A service exited with an error during shutdown.", name)

    def stop_all(self, order: Sequence[str], stop_postgres: Callable[[], None] | None = None) -> None:
        for name in order:
            if name == "postgres" and stop_postgres is not None:
                stop_postgres()
            else:
                self.stop(name)

    def alive_names(self) -> tuple[str, ...]:
        return tuple(name for name, child in self.processes.items() if child.process.poll() is None)


@contextmanager
def instance_lock(path: Path) -> Iterator[None]:
    if _is_reparse_point(path):
        raise RuntimeFailure("LOCK_PATH_UNSAFE", "The per-user runtime lock cannot be a link or junction.")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError as error:
                raise RuntimeAlreadyActive() from error
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as error:
                raise RuntimeAlreadyActive() from error
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def runtime_is_active(paths: ProjectaPaths) -> bool:
    try:
        with instance_lock(paths.lock_file):
            return False
    except RuntimeAlreadyActive:
        return True


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_json(path: Path, value: object) -> None:
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def load_json(path: Path, code: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeFailure(code, "A local Projecta state file is missing or invalid.") from error
    if not isinstance(value, dict):
        raise RuntimeFailure(code, "A local Projecta state file is missing or invalid.")
    return value


def _verify_package_inventory(
    package_root: Path,
    manifest: Mapping[str, object],
    *,
    error_code: str,
) -> None:
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise RuntimeFailure(error_code, "The package file manifest is missing or invalid.")
    expected: dict[str, Mapping[str, object]] = {}
    normalized: set[str] = set()
    for raw in raw_files:
        if not isinstance(raw, dict) or set(raw) != {"path", "size", "sha256"}:
            raise RuntimeFailure(error_code, "The package file manifest contains an invalid entry.")
        relative = raw.get("path")
        size = raw.get("size")
        digest = raw.get("sha256")
        if (
            not isinstance(relative, str)
            or "\\" in relative
            or not _is_safe_relative_path(relative)
            or PurePosixPath(relative).as_posix() != relative
            or relative in {"runtime-manifest.json", "runtime-manifest.sig"}
            or type(size) is not int
            or size < 0
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or relative.casefold() in normalized
        ):
            raise RuntimeFailure(error_code, "The package file manifest contains an invalid entry.")
        normalized.add(relative.casefold())
        expected[relative] = raw

    if _is_reparse_point(package_root) or not package_root.is_dir():
        raise RuntimeFailure(error_code, "The package directory is invalid.")
    root = package_root.resolve()
    actual: dict[str, Path] = {}
    try:
        for path in package_root.rglob("*"):
            if _is_reparse_point(path):
                raise RuntimeFailure(error_code, "The package contains an unsafe linked path.")
            if not path.is_file():
                continue
            if _is_msvc_runtime_dll(path):
                raise RuntimeFailure(error_code, "The package contains a prohibited Microsoft Visual C++ runtime DLL.")
            if _is_vc_runtime_installer(path):
                raise RuntimeFailure(error_code, "The Microsoft Visual C++ Redistributable installer must not be bundled in the package.")
            relative = path.relative_to(package_root).as_posix()
            if relative not in {"runtime-manifest.json", "runtime-manifest.sig"}:
                resolved = path.resolve(strict=True)
                if root not in resolved.parents:
                    raise RuntimeFailure(error_code, "The package contains an unsafe linked path.")
                actual[relative] = path
    except OSError as error:
        raise RuntimeFailure(error_code, "The package contents could not be read safely.") from error
    if set(actual) != set(expected):
        raise RuntimeFailure(error_code, "The package is incomplete or contains unmanifested files.")
    for relative, entry in expected.items():
        path = actual[relative]
        try:
            if path.stat().st_size != entry["size"] or _file_sha256(path) != entry["sha256"]:
                raise RuntimeFailure(error_code, "A package file does not match its integrity manifest.")
        except OSError as error:
            raise RuntimeFailure(error_code, "A package file could not be verified.") from error


def _release_public_key(encoded_key: str | None = None) -> bytes:
    encoded = encoded_key if encoded_key is not None else RELEASE_UPDATE_PUBLIC_KEY_B64
    if not isinstance(encoded, str) or not encoded:
        raise RuntimeFailure(
            "UPDATE_TRUST_ANCHOR_MISSING",
            "This launcher has no owner release-verification key; updates remain disabled.",
        )
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise RuntimeFailure("UPDATE_TRUST_ANCHOR_INVALID", "The release-verification key is invalid.") from error
    if len(key) != 32:
        raise RuntimeFailure("UPDATE_TRUST_ANCHOR_INVALID", "The release-verification key is invalid.")
    return key


def _verify_ed25519_signature(manifest_bytes: bytes, signature_path: Path, public_key: bytes) -> None:
    if _is_reparse_point(signature_path):
        raise RuntimeFailure("UPDATE_SIGNATURE_INVALID", "The update package signature is invalid.")
    try:
        signature_bytes = base64.b64decode(signature_path.read_bytes().strip(), validate=True)
    except (OSError, ValueError, base64.binascii.Error) as error:
        raise RuntimeFailure("UPDATE_SIGNATURE_INVALID", "The update package signature is invalid.") from error
    if len(signature_bytes) != 64:
        raise RuntimeFailure("UPDATE_SIGNATURE_INVALID", "The update package signature is invalid.")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        Ed25519PublicKey.from_public_bytes(public_key).verify(signature_bytes, manifest_bytes)
    except ImportError as error:
        raise RuntimeFailure("UPDATE_CRYPTO_UNAVAILABLE", "Signature verification is unavailable in this launcher.") from error
    except (InvalidSignature, ValueError) as error:
        raise RuntimeFailure("UPDATE_SIGNATURE_INVALID", "The update package signature is invalid.") from error


def _verify_manifest_signature(package_root: Path, manifest_bytes: bytes) -> None:
    signature_path = package_root / "runtime-manifest.sig"
    if not signature_path.is_file():
        raise RuntimeFailure("UPDATE_SIGNATURE_REQUIRED", "The package is unsigned and cannot be treated as a release.")
    _verify_ed25519_signature(manifest_bytes, signature_path, _release_public_key())


def _version_tuple(value: object) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise RuntimeFailure("UPDATE_PACKAGE_INVALID", "The package version is invalid.")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def load_runtime_manifest(
    paths: ProjectaPaths,
    *,
    expected_project_version: str = APP_VERSION,
) -> dict[str, object]:
    manifest = load_json(paths.runtime_manifest, "PACKAGE_MANIFEST_INVALID")
    versions = manifest.get("runtimeVersions")
    if manifest.get("formatVersion") != 1 or manifest.get("projectaVersion") != expected_project_version:
        raise RuntimeFailure("PACKAGE_MANIFEST_INVALID", "The bundled runtime manifest is not supported.")
    if versions != RUNTIME_VERSIONS:
        raise RuntimeFailure("PACKAGE_VERSION_UNSUPPORTED", "The bundled runtime versions do not match this launcher.")
    if type(manifest.get("dataContractVersion")) is not int or manifest["dataContractVersion"] < 1:
        raise RuntimeFailure("PACKAGE_MANIFEST_INVALID", "The bundled data contract version is not supported.")
    if type(manifest.get("releaseEligible")) is not bool:
        raise RuntimeFailure("PACKAGE_MANIFEST_INVALID", "The bundled release status is invalid.")
    channel = manifest.get("distributionChannel")
    signature_path = paths.package_root / "runtime-manifest.sig"
    if manifest["releaseEligible"]:
        if channel != "signed-release" or "unsignedPreReleaseException" in manifest:
            raise RuntimeFailure("PACKAGE_MANIFEST_INVALID", "The signed release channel is invalid.")
        manifest_bytes = paths.runtime_manifest.read_bytes()
        _verify_manifest_signature(paths.package_root, manifest_bytes)
    elif channel == "host-validation":
        if "unsignedPreReleaseException" in manifest or signature_path.exists():
            raise RuntimeFailure("PACKAGE_MANIFEST_INVALID", "The host-validation package metadata is invalid.")
    elif channel == UNSIGNED_PRE_RELEASE_CHANNEL:
        if (
            APP_VERSION != UNSIGNED_PRE_RELEASE_VERSION
            or manifest.get("projectaVersion") != UNSIGNED_PRE_RELEASE_VERSION
            or manifest.get("unsignedPreReleaseException") != UNSIGNED_PRE_RELEASE_EXCEPTION
            or signature_path.exists()
        ):
            raise RuntimeFailure("PACKAGE_MANIFEST_INVALID", "The unsigned pre-release exception is invalid.")
    else:
        raise RuntimeFailure("PACKAGE_MANIFEST_INVALID", "The bundled distribution channel is invalid.")
    _verify_package_inventory(paths.package_root, manifest, error_code="PACKAGE_CONTENT_INVALID")
    _validate_vc_runtime_prerequisite(
        paths.package_root,
        manifest,
        error_code="PACKAGE_MANIFEST_INVALID",
    )
    if not (paths.package_root / "ProjectaStart.ps1").is_file():
        raise RuntimeFailure("PACKAGE_RUNTIME_INCOMPLETE", "The prerequisite-safe Projecta launcher is absent.")
    notices = manifest.get("noticeFiles")
    if not isinstance(notices, list) or not notices:
        raise RuntimeFailure("PACKAGE_NOTICES_MISSING", "Third-party runtime notices are missing from the package.")
    for notice in notices:
        if not isinstance(notice, str) or not _is_safe_relative_path(notice):
            raise RuntimeFailure("PACKAGE_NOTICES_INVALID", "The package notice index is invalid.")
        if not (paths.package_root / notice).is_file():
            raise RuntimeFailure("PACKAGE_NOTICES_MISSING", "A required third-party notice is absent from the package.")
    if channel == UNSIGNED_PRE_RELEASE_CHANNEL and "runtime/installer-tool/NSIS-COPYING.txt" not in notices:
        raise RuntimeFailure("PACKAGE_NOTICES_MISSING", "The installer license notice is absent from the pre-release package.")
    required_files = (
        paths.runtime / "python" / "python.exe",
        paths.runtime / "python" / "python312._pth",
        paths.runtime / "java" / "bin" / "java.exe",
        paths.runtime / "postgresql" / "bin" / "initdb.exe",
        paths.runtime / "postgresql" / "bin" / "postgres.exe",
        paths.runtime / "postgresql" / "bin" / "pg_ctl.exe",
        paths.runtime / "postgresql" / "bin" / "createdb.exe",
        paths.runtime / "postgresql" / "bin" / "pg_isready.exe",
        paths.runtime / "postgresql" / "bin" / "psql.exe",
        paths.project / "api" / "src" / "projecta_api" / "main.py",
        paths.project / "api" / "alembic.ini",
        paths.project / "api" / "alembic" / "env.py",
        paths.project / "semantic-core" / "classes" / "org" / "projecta" / "semanticcore" / "SemanticCoreApplication.class",
        paths.project / "semantic-core" / "classes" / "org" / "projecta" / "semanticcore" / "LocalFusekiServer.class",
        paths.project / "fuseki-config.template.ttl",
        paths.project / "scripts" / "bootstrap_fuseki.py",
        paths.project / "ontology" / "core.ttl",
        paths.project / "web" / "index.html",
        paths.package_root / "THIRD-PARTY-NOTICES.md",
        paths.package_root / "runtime" / "python" / "uv.lock",
        paths.package_root / "runtime" / "python" / "wheel-requirements.txt",
        paths.runtime / "vc-runtime-policy.json",
        paths.runtime / "vc_runtime_prerequisite.ps1",
        paths.package_root / "ProjectaLocal.exe",
        paths.package_root / "Projecta.exe",
    )
    template_ok = (paths.project / "fuseki-config.template.ttl").is_file() or (
        paths.project / "fuseki-config.ttl"
    ).is_file()
    remaining = [path for path in required_files if path.name != "fuseki-config.template.ttl"]
    if not template_ok or any(not path.is_file() for path in remaining):
        raise RuntimeFailure("PACKAGE_RUNTIME_INCOMPLETE", "A required bundled runtime or application file is absent.")
    jena_runtime = paths.project / "semantic-core" / "lib" / f"jena-fuseki-main-{RUNTIME_VERSIONS['fuseki']}.jar"
    if not jena_runtime.is_file():
        raise RuntimeFailure("PACKAGE_RUNTIME_INCOMPLETE", "The pinned Fuseki server runtime is absent.")
    return manifest

def _is_staged_runtime() -> bool:
    return not getattr(sys, "frozen", False) and bool(
        os.environ.get("PROJECTA_LAUNCHER_PACKAGE_ROOT")
        and os.environ.get("PROJECTA_LAUNCHER_DATA_ROOT")
    )


def _require_package_distribution(manifest: Mapping[str, object]) -> None:
    if manifest.get("releaseEligible") is True:
        return
    if (
        APP_VERSION == UNSIGNED_PRE_RELEASE_VERSION
        and manifest.get("projectaVersion") == UNSIGNED_PRE_RELEASE_VERSION
        and manifest.get("releaseEligible") is False
        and manifest.get("distributionChannel") == UNSIGNED_PRE_RELEASE_CHANNEL
        and manifest.get("unsignedPreReleaseException") == UNSIGNED_PRE_RELEASE_EXCEPTION
    ):
        return
    raise RuntimeFailure(
        "PACKAGE_SIGNATURE_REQUIRED",
        "This unsigned host-validation package is not enabled for the 0.7.0 test pre-release.",
    )




def _is_safe_relative_path(value: str) -> bool:
    candidate = PurePosixPath(value.replace("\\", "/"))
    return not candidate.is_absolute() and all(part not in {"", ".", ".."} for part in candidate.parts)


FIRST_RUN_DISPLAY_NAME = "My Projecta Workspace"
FIRST_RUN_ACTOR_ID = "local-operator"


def _slugify_first_run_project_id(display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", display_name.strip().lower()).strip("-")
    if not slug:
        slug = "projecta-workspace"
    if slug[0].isdigit():
        slug = f"project-{slug}"
    return slug[:63]


def provision_first_run_workspace(path: Path, *, display_name: str = FIRST_RUN_DISPLAY_NAME) -> WorkspaceConfig:
    """Write the approved first-run workspace config once, on a fresh data directory only."""
    name = display_name.strip()
    if not name or len(name) > 128 or any(ord(character) < 32 for character in name):
        raise RuntimeFailure("LOCAL_PROJECT_CONFIGURATION_INVALID", "The first-run workspace display name is invalid.")
    project_id = _slugify_first_run_project_id(name)
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise RuntimeFailure("LOCAL_PROJECT_CONFIGURATION_INVALID", "The generated first-run project ID is invalid.")
    if path.exists():
        raise RuntimeFailure("LOCAL_PROJECT_CONFIGURATION_INVALID", "First-run provisioning must not overwrite existing workspace configuration.")
    atomic_json(
        path,
        {
            "formatVersion": 1,
            "projectId": project_id,
            "projectName": name,
            "actorId": FIRST_RUN_ACTOR_ID,
        },
    )
    return WorkspaceConfig(project_id, name, FIRST_RUN_ACTOR_ID)


def read_workspace_config(path: Path, *, provision_first_run: bool = False) -> WorkspaceConfig:
    if not path.is_file():
        if provision_first_run:
            return provision_first_run_workspace(path)
        raise RuntimeFailure(
            "FIRST_RUN_SETUP_REQUIRED",
            "No local workspace exists yet; run install or start once to provision the approved first-run workspace on a fresh data directory.",
        )
    value = load_json(path, "LOCAL_PROJECT_CONFIGURATION_INVALID")
    project_id = value.get("projectId")
    project_name = value.get("projectName")
    actor_id = value.get("actorId")
    if (
        value.get("formatVersion") != 1
        or not isinstance(project_id, str)
        or not PROJECT_ID_PATTERN.fullmatch(project_id)
        or not isinstance(project_name, str)
        or not project_name.strip()
        or len(project_name) > 128
        or any(ord(character) < 32 for character in project_name)
        or not isinstance(actor_id, str)
        or not ACTOR_ID_PATTERN.fullmatch(actor_id)
    ):
        raise RuntimeFailure("LOCAL_PROJECT_CONFIGURATION_INVALID", "The local project configuration is invalid.")
    return WorkspaceConfig(project_id, project_name.strip(), actor_id)


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, *, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeFailure("DPAPI_UNAVAILABLE", "CurrentUser DPAPI is available only on Windows.")
    input_buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    input_blob = _DataBlob(len(data), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output_blob = _DataBlob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if decrypt:
        description = ctypes.wintypes.LPWSTR()
        function = crypt32.CryptUnprotectData
        function.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.POINTER(ctypes.wintypes.LPWSTR),
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        ]
        succeeded = function(
            ctypes.byref(input_blob),
            ctypes.byref(description),
            None,
            None,
            None,
            1,
            ctypes.byref(output_blob),
        )
    else:
        function = crypt32.CryptProtectData
        function.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.wintypes.LPCWSTR,
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        ]
        succeeded = function(ctypes.byref(input_blob), "Projecta Local runtime secrets", None, None, None, 1, ctypes.byref(output_blob))
    if not succeeded:
        raise RuntimeFailure("DPAPI_OPERATION_FAILED", "Windows CurrentUser secret protection failed.")
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
        if decrypt and description:
            kernel32.LocalFree(description)


def generate_runtime_secrets() -> RuntimeSecrets:
    key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    return RuntimeSecrets(
        postgres_password=base64.urlsafe_b64encode(os.urandom(36)).decode("ascii").rstrip("="),
        trusted_context_secret=base64.urlsafe_b64encode(os.urandom(36)).decode("ascii").rstrip("="),
        secret_store_master_key=key,
    )


def protect_runtime_secrets(path: Path, secrets_value: RuntimeSecrets) -> None:
    serialized = json.dumps(
        {
            "postgresPassword": secrets_value.postgres_password,
            "trustedContextSecret": secrets_value.trusted_context_secret,
            "secretStoreMasterKey": secrets_value.secret_store_master_key,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    atomic_write(path, _dpapi(serialized, decrypt=False))


def unprotect_runtime_secrets(path: Path) -> RuntimeSecrets:
    try:
        protected = path.read_bytes()
    except OSError as error:
        raise RuntimeFailure("SECRET_STORE_RECOVERY_REQUIRED", "The local DPAPI secret file is missing.") from error
    try:
        serialized = _dpapi(protected, decrypt=True).decode("utf-8")
    except RuntimeFailure as error:
        raise RuntimeFailure("SECRET_STORE_RECOVERY_REQUIRED", "The local DPAPI secrets cannot be opened by this Windows account.") from error
    try:
        value = json.loads(serialized)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeFailure("SECRET_STORE_RECOVERY_REQUIRED", "The local DPAPI secret file is corrupt.") from error
    if not isinstance(value, dict):
        raise RuntimeFailure("SECRET_STORE_RECOVERY_REQUIRED", "The local DPAPI secret file is corrupt.")
    secret_values = (
        value.get("postgresPassword"),
        value.get("trustedContextSecret"),
        value.get("secretStoreMasterKey"),
    )
    if any(not isinstance(secret, str) or not secret for secret in secret_values):
        raise RuntimeFailure("SECRET_STORE_RECOVERY_REQUIRED", "The local DPAPI secret file is corrupt.")
    return RuntimeSecrets(
        postgres_password=secret_values[0],
        trusted_context_secret=secret_values[1],
        secret_store_master_key=secret_values[2],
    )

def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _append_safe_log(path: Path, event: str, *, code: str | None = None, service: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [f"{_utc_now()} event={event}"]
    if service:
        fields.append(f"service={service}")
    if code:
        fields.append(f"code={code}")
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(" ".join(fields) + "\n")


def _clear_inherited_secrets(environment: Mapping[str, str]) -> dict[str, str]:
    result = dict(environment)
    prefixes = (
        "PROJECTA_",
        "FUSEKI_",
        "SEMANTIC_CORE_",
        "ONTOLOGY_DIRECTORY",
        "PGPASSWORD",
        "PGUSER",
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "OPENAI_",
        "ANTHROPIC_",
        "COHERE_",
        "AZURE_OPENAI_",
        "AWS_",
        "GOOGLE_",
        "GCP_",
        "HF_",
        "HUGGINGFACE_",
    )
    secret_names = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "CLASSPATH"}
    for name in tuple(result):
        upper = name.upper()
        if upper.startswith(prefixes) or upper in secret_names:
            result.pop(name, None)
    return result


def _exclusive_loopback_port(port: int) -> bool:
    family = socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _http_probe(
    url: str,
    *,
    timeout: float = HTTP_PROBE_TIMEOUT_SECONDS,
    capture_error_body: bool = False,
) -> HttpProbeResult:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.monotonic()
    try:
        with opener.open(url, timeout=timeout) as response:
            return HttpProbeResult(response.status, None, None, int((time.monotonic() - started) * 1000))
    except urllib.error.HTTPError as error:
        body = error.read(HEALTH_RESPONSE_BODY_LIMIT).decode("utf-8", "replace") if capture_error_body else None
        return HttpProbeResult(error.code, body, None, int((time.monotonic() - started) * 1000))
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        failure = "timeout" if isinstance(reason, TimeoutError) else "connection-error"
        return HttpProbeResult(None, None, failure, int((time.monotonic() - started) * 1000))


def _safe_health_response(body: str) -> str | None:
    try:
        response = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(response, dict):
        return None
    safe: dict[str, object] = {}
    for name in ("status", "semanticCore", "oidc"):
        value = response.get(name)
        if isinstance(value, str) and value in {"ready", "not-ready", "unavailable"}:
            safe[name] = value
    reason_code = response.get("reasonCode")
    if isinstance(reason_code, str) and re.fullmatch(r"[A-Z0-9_-]{1,64}", reason_code):
        safe["reasonCode"] = reason_code
    problems = response.get("problems")
    if (
        isinstance(problems, list)
        and len(problems) <= 32
        and all(isinstance(problem, str) and re.fullmatch(r"[A-Z0-9_-]{1,64}", problem) for problem in problems)
    ):
        safe["problems"] = problems
    return json.dumps(safe, sort_keys=True, separators=(",", ":")) if safe else None


def _append_readiness_failure(path: Path, service: str, timeout: float, probe: HttpProbeResult) -> None:
    fields = [
        f"{_utc_now()} event=readiness-probe-failed",
        f"service={service}",
        f"timeoutMs={int(timeout * 1000)}",
        f"elapsedMs={probe.elapsed_ms}",
        f"httpStatus={probe.status_code if probe.status_code is not None else 'none'}",
    ]
    if probe.failure:
        fields.append(f"probeFailure={probe.failure}")
    if probe.response_body is not None:
        response = _safe_health_response(probe.response_body)
        if response is not None:
            fields.append(f"response={response}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(" ".join(fields) + "\n")


def _require_windows_11_x64() -> None:
    if os.name != "nt" or struct.calcsize("P") != 8 or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeFailure("PLATFORM_UNSUPPORTED", "Projecta Local supports Windows 11 x64 only.")
    version = sys.getwindowsversion()
    if version.build < 22000 or version.product_type != 1:
        raise RuntimeFailure("PLATFORM_UNSUPPORTED", "Projecta Local supports Windows 11 x64 only.")


class RuntimeManager:
    def __init__(self, paths: ProjectaPaths, *, open_browser: bool = True) -> None:
        self.paths = paths
        self.open_browser = open_browser
        self.host = ProcessHost()
        self.runtime_id = uuid.uuid4().hex
        self.workspace: WorkspaceConfig | None = None
        self.secrets: RuntimeSecrets | None = None
        self.manifest: dict[str, object] | None = None
        self._failure: RuntimeFailure | None = None

    def start(self) -> int:
        _require_windows_11_x64()
        self.paths.ensure_user_directories()
        with instance_lock(self.paths.lock_file):
            self._write_status("starting")
            print("Starting Projecta Local: PostgreSQL, Fuseki, Semantic Core, and API.")
            _append_safe_log(self.paths.log_file, "startup")
            try:
                self.manifest = load_runtime_manifest(self.paths)
                _require_package_distribution(self.manifest)
                self.workspace = read_workspace_config(self.paths.local_config, provision_first_run=True)
                self.secrets = unprotect_runtime_secrets(self.paths.protected_secrets)
                self._validate_installation()
                self._start_dependencies()
                self._run_database_setup()
                self._run_fuseki_bootstrap()
                self._start_semantic_core()
                self._start_api()
                self._write_status("ready")
                print(f"Projecta Local is ready at http://127.0.0.1:{PORTS['api']}/")
                _append_safe_log(self.paths.log_file, "ready")
                self._open_browser()
                self._supervise()
            except KeyboardInterrupt:
                _append_safe_log(self.paths.log_file, "keyboard-stop-requested")
            except RuntimeFailure as error:
                self._failure = error
                print(f"Projecta Local: {error.message} [{error.code}]", file=sys.stderr)
                _append_safe_log(self.paths.log_file, "failure", code=error.code, service=error.service)
            except Exception:
                self._failure = RuntimeFailure(
                    "RUNTIME_INTERNAL_ERROR",
                    "The runtime manager failed safely; service output was suppressed.",
                )
                print(f"Projecta Local: {self._failure.message} [{self._failure.code}]", file=sys.stderr)
                _append_safe_log(self.paths.log_file, "failure", code=self._failure.code)
            stop_error = self._stop_owned_processes()
            if stop_error is not None:
                self._failure = self._failure or stop_error
                self._wait_for_graceful_stop_retry()
            final_state = "failed" if self._failure else "stopped"
            self._write_status(final_state, failure=self._failure)
            if self._failure is None:
                print("Projecta Local stopped. All persistent state was retained.")
            _append_safe_log(
                self.paths.log_file,
                final_state,
                code=self._failure.code if self._failure else None,
                service=self._failure.service if self._failure else None,
            )
            return 1 if self._failure else 0

    def _validate_installation(self) -> None:
        if self.manifest is None or self.workspace is None or self.secrets is None:
            raise RuntimeFailure("LOCAL_INSTALLATION_INVALID", "The local installation is incomplete.")
        installation = load_json(self.paths.installation_config, "LOCAL_INSTALLATION_INVALID")
        if (
            self.manifest is None
            or installation.get("runtimeVersions") != self.manifest.get("runtimeVersions")
            or installation.get("dataContractVersion", DATA_CONTRACT_VERSION)
            != self.manifest.get("dataContractVersion")
        ):
            raise RuntimeFailure("UPDATE_RECOVERY_REQUIRED", "The installed runtime does not match its local data contract.")
        for port in PORTS.values():
            if not _exclusive_loopback_port(port):
                raise RuntimeFailure("PORT_IN_USE", "A required loopback port is occupied; Projecta will not choose another port.")
        self.paths.data.joinpath("postgres").mkdir(parents=True, exist_ok=True)
        self.paths.data.joinpath("fuseki", "databases", "projecta").mkdir(parents=True, exist_ok=True)

    def _environment(self) -> dict[str, str]:
        java_home = self.paths.runtime / "java"
        postgres_bin = self.paths.runtime / "postgresql" / "bin"
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        path_value = os.pathsep.join((str(java_home / "bin"), str(postgres_bin), str(Path(system_root) / "System32"), system_root))
        environment = _clear_inherited_secrets(os.environ)
        environment.update(
            {
                "PATH": path_value,
                "JAVA_HOME": str(java_home),
                "PGDATA": str(self.paths.data / "postgres"),
                "PGSHAREDIR": str(self.paths.runtime / "postgresql" / "share"),
                "FUSEKI_BASE": str(self.paths.data / "fuseki"),
            }
        )
        return environment

    def _initialize_postgres(self, environment: Mapping[str, str]) -> None:
        data_path = self.paths.data / "postgres"
        version_file = data_path / "PG_VERSION"
        if version_file.is_file():
            try:
                version = version_file.read_text(encoding="ascii").strip()
            except OSError as error:
                raise RuntimeFailure("POSTGRES_STATE_INVALID", "PostgreSQL state cannot be read.", "postgres") from error
            if version != "16":
                raise RuntimeFailure("POSTGRES_VERSION_MISMATCH", "Existing PostgreSQL state is not version 16.", "postgres")
            return
        if any(data_path.iterdir()):
            raise RuntimeFailure("POSTGRES_STATE_INVALID", "PostgreSQL data exists without a valid version marker.", "postgres")
        if self.secrets is None:
            raise RuntimeFailure("SECRET_STORE_RECOVERY_REQUIRED", "Local PostgreSQL credentials are unavailable.")
        password_file = self.paths.config / f"postgres-init-{self.runtime_id}.tmp"
        atomic_write(password_file, (self.secrets.postgres_password + "\n").encode("ascii"))
        try:
            self.host.run_task(
                "postgres",
                [
                    str(self.paths.runtime / "postgresql" / "bin" / "initdb.exe"),
                    "--encoding=UTF8",
                    "--username=projecta",
                    "--auth-host=scram-sha-256",
                    "--auth-local=trust",
                    f"--pwfile={password_file}",
                    f"--pgdata={data_path}",
                ],
                environment,
                self.paths.runtime / "postgresql",
                timeout=180,
            )
        finally:
            password_file.unlink(missing_ok=True)
        if not version_file.is_file():
            raise RuntimeFailure("POSTGRES_INIT_FAILED", "PostgreSQL initialization did not produce a valid data directory.", "postgres")

    def _start_dependencies(self) -> None:
        if self.workspace is None:
            raise RuntimeFailure("LOCAL_PROJECT_CONFIGURATION_INVALID", "The local project configuration is missing.")
        environment = self._environment()
        self._initialize_postgres(environment)
        postgres = self.paths.runtime / "postgresql" / "bin" / "postgres.exe"
        pg_env = dict(environment)
        self.host.start(
            "postgres",
            [str(postgres), "-D", str(self.paths.data / "postgres"), "-h", "127.0.0.1", "-p", str(PORTS["postgres"])],
            pg_env,
            self.paths.runtime / "postgresql",
            control_pipe=False,
        )
        self._start_fuseki(environment)
        self._wait_postgres_ready()
        # Embedded Fuseki serves only the configured dataset (no $/ admin paths):
        # readiness is a live SPARQL answer from the projecta dataset itself.
        self._wait_http_ready(
            "fuseki",
            f"http://127.0.0.1:{PORTS['fuseki']}/projecta/query?query=ASK%7B%7D",
            90,
        )

    def _fuseki_config(self) -> Path:
        template_path = self.paths.project / "fuseki-config.template.ttl"
        if not template_path.is_file():
            fallback = self.paths.project / "fuseki-config.ttl"
            if fallback.is_file():
                template_path = fallback
        try:
            template = template_path.read_text(encoding="utf-8")
        except OSError as error:
            raise RuntimeFailure("PACKAGE_CONFIGURATION_INVALID", "The packaged Fuseki configuration is missing.", "fuseki") from error
        old_location = '"/var/lib/fuseki/databases/projecta"'
        if template.count(old_location) != 1:
            raise RuntimeFailure("PACKAGE_CONFIGURATION_INVALID", "The packaged Fuseki configuration template is invalid.", "fuseki")
        target_location = self.paths.data / "fuseki" / "databases" / "projecta"
        config_path = self.paths.config / "fuseki-config.ttl"
        atomic_write(config_path, template.replace(old_location, json.dumps(str(target_location))).encode("utf-8"))
        return config_path

    def _start_fuseki(self, environment: Mapping[str, str]) -> None:
        java = self.paths.runtime / "java" / "bin" / "java.exe"
        classes = self.paths.project / "semantic-core" / "classes"
        libraries = self.paths.project / "semantic-core" / "lib" / "*"
        classpath = f"{classes}{os.pathsep}{libraries}"
        self.host.start(
            "fuseki",
            [
                str(java),
                "-cp",
                classpath,
                "org.projecta.semanticcore.LocalFusekiServer",
                str(PORTS["fuseki"]),
                str(self._fuseki_config()),
            ],
            environment,
            self.paths.project / "semantic-core",
        )

    def _wait_postgres_ready(self, timeout: float = 90.0) -> None:
        binary = self.paths.runtime / "postgresql" / "bin" / "pg_isready.exe"
        environment = self._environment()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.host.check_alive("postgres")
            try:
                result = subprocess.run(
                    [
                        str(binary),
                        "--host=127.0.0.1",
                        f"--port={PORTS['postgres']}",
                        "--username=projecta",
                        "--dbname=postgres",
                    ],
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                result = None
            if result is not None and result.returncode == 0:
                return
            time.sleep(0.5)
        raise RuntimeFailure("SERVICE_READINESS_TIMEOUT", "PostgreSQL did not become ready.", "postgres")

    def _run_database_setup(self) -> None:
        if self.secrets is None:
            raise RuntimeFailure("SECRET_STORE_RECOVERY_REQUIRED", "Local PostgreSQL credentials are unavailable.")
        environment = self._environment()
        pg_client_environment = dict(environment)
        pg_client_environment["PGPASSWORD"] = self.secrets.postgres_password
        psql = self.paths.runtime / "postgresql" / "bin" / "psql.exe"
        query = "SELECT 1 FROM pg_database WHERE datname = 'projecta';"
        exists = self.host.run_task(
            "postgres",
            [
                str(psql),
                "-X",
                "-A",
                "-t",
                "--host=127.0.0.1",
                f"--port={PORTS['postgres']}",
                "--username=projecta",
                "--dbname=postgres",
                f"--command={query}",
            ],
            pg_client_environment,
            self.paths.runtime / "postgresql",
            timeout=30,
            capture_stdout=True,
        )
        if exists.strip() != "1":
            createdb = self.paths.runtime / "postgresql" / "bin" / "createdb.exe"
            self.host.run_task(
                "postgres",
                [
                    str(createdb),
                    "--host=127.0.0.1",
                    f"--port={PORTS['postgres']}",
                    "--username=projecta",
                    "--no-password",
                    "projecta",
                ],
                pg_client_environment,
                self.paths.runtime / "postgresql",
                timeout=30,
            )
        api_root = self.paths.project / "api"
        self.host.run_task(
            "api-migrations",
            self._python_module_command("projecta_api.operational.migrate", "upgrade"),
            self._api_environment(environment),
            api_root,
            timeout=180,
        )

    def _run_fuseki_bootstrap(self) -> None:
        python = self.paths.runtime / "python" / "python.exe"
        scripts = self.paths.project / "scripts"
        environment = self._environment()
        if self.workspace is None:
            raise RuntimeFailure("LOCAL_PROJECT_CONFIGURATION_INVALID", "The local project configuration is missing.")
        environment.update(
            {
                "FUSEKI_DATASET_URL": f"http://127.0.0.1:{PORTS['fuseki']}/projecta",
                "ONTOLOGY_DIRECTORY": str(self.paths.project / "ontology"),
                "PROJECTA_FUSEKI_BOOTSTRAP_MARKER_FILE": str(self.paths.data / "fuseki" / "projecta-bootstrap.json"),
                "PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS": f"{self.workspace.project_id}|{self.workspace.project_name}",
            }
        )
        self.host.run_task(
            "fuseki-bootstrap",
            [str(python), str(scripts / "bootstrap_fuseki.py")],
            environment,
            scripts,
            timeout=180,
        )

    def _start_semantic_core(self) -> None:
        java = self.paths.runtime / "java" / "bin" / "java.exe"
        classes = self.paths.project / "semantic-core" / "classes"
        libraries = self.paths.project / "semantic-core" / "lib" / "*"
        classpath = f"{classes}{os.pathsep}{libraries}"
        environment = self._environment()
        environment.update(
            {
                "FUSEKI_BASE_URL": f"http://127.0.0.1:{PORTS['fuseki']}/projecta",
                "SEMANTIC_CORE_HOST": "127.0.0.1",
                "SEMANTIC_CORE_PORT": str(PORTS["semanticCore"]),
                "PROJECTA_SHAPES_DIRECTORY": str(self.paths.project / "ontology" / "shapes"),
                "PROJECTA_LOCAL_CONTROL_PIPE": "1",
            }
        )
        self.host.start(
            "semanticCore",
            [str(java), "-cp", classpath, "org.projecta.semanticcore.SemanticCoreApplication"],
            environment,
            self.paths.project / "semantic-core",
        )
        self._wait_http_ready(
            "semanticCore", f"http://127.0.0.1:{PORTS['semanticCore']}/health/ready", 90
        )

    def _python_module_command(self, module: str, *args: str) -> list[str]:
        # The CPython embeddable distribution ignores PYTHONPATH and does not
        # prepend the working directory: its python312._pth file fully defines
        # sys.path. Insert the staged API source tree explicitly so the bundled
        # interpreter resolves projecta_api without touching the install tree.
        python = self.paths.runtime / "python" / "python.exe"
        api_source = self.paths.project / "api" / "src"
        bootstrap = (
            "import runpy, sys; "
            f"sys.path.insert(0, {str(api_source)!r}); "
            f"runpy.run_module({module!r}, run_name='__main__', alter_sys=True)"
        )
        return [str(python), "-X", "utf8", "-c", bootstrap, *args]

    def _api_environment(self, base: Mapping[str, str] | None = None) -> dict[str, str]:
        if self.secrets is None or self.workspace is None:
            raise RuntimeFailure("LOCAL_PROJECT_CONFIGURATION_INVALID", "The local project configuration is incomplete.")
        environment = dict(base) if base is not None else self._environment()
        site_packages = self.paths.runtime / "python" / "Lib" / "site-packages"
        api_source = self.paths.project / "api" / "src"
        environment.update(
            {
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": os.pathsep.join((str(api_source), str(site_packages))),
                # NOTE: the embeddable interpreter ignores PYTHONPATH (python312._pth
                # owns sys.path); child commands bootstrap sys.path explicitly.
                "PROJECTA_API_SEMANTIC_CORE_URL": f"http://127.0.0.1:{PORTS['semanticCore']}",
                "PROJECTA_API_TRUSTED_CONTEXT_SECRET": self.secrets.trusted_context_secret,
                "PROJECTA_API_RUNTIME_MODE": "experience",
                "PROJECTA_API_OPERATIONAL_DATABASE_PATH": str(self.paths.data / "sqlite" / "operational.db"),
                "PROJECTA_CONNECTOR_DATABASE_HOST": "127.0.0.1",
                "PROJECTA_CONNECTOR_DATABASE_PORT": str(PORTS["postgres"]),
                "PROJECTA_CONNECTOR_DATABASE_NAME": "projecta",
                "PROJECTA_CONNECTOR_DATABASE_USER": "projecta",
                "PROJECTA_CONNECTOR_DATABASE_PASSWORD": self.secrets.postgres_password,
                "PROJECTA_EVIDENCE_ROOT": str(self.paths.data / "evidence"),
                "PROJECTA_API_SECRET_STORE_MASTER_KEY": self.secrets.secret_store_master_key,
                "PROJECTA_API_EXPERIENCE_ACTOR_ID": self.workspace.actor_id,
                "PROJECTA_API_EXPERIENCE_PROJECT_CATALOG": self.workspace.project_id,
                "PROJECTA_API_WEB_ASSETS_DIRECTORY": str(self.paths.project / "web"),
                "PROJECTA_API_PORTABLE_EXPORT_LOCK_HELD": "true",
            }
        )
        return environment

    def _start_api(self) -> None:
        environment = self._api_environment()
        api_root = self.paths.project / "api"
        self.host.start(
            "api",
            self._python_module_command("projecta_api.local_server"),
            environment,
            api_root,
        )
        self._wait_http_ready("api", f"http://127.0.0.1:{PORTS['api']}/health/ready", 90)

    def _wait_http_ready(self, service: str, url: str, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        probe_timeout = READINESS_PROBE_TIMEOUTS.get(service, HTTP_PROBE_TIMEOUT_SECONDS)
        last_probe: HttpProbeResult | None = None
        while time.monotonic() < deadline:
            self.host.check_alive(service)
            last_probe = _http_probe(url, timeout=probe_timeout, capture_error_body=service == "api")
            if last_probe.status_code == 200:
                return
            time.sleep(0.5)
        if last_probe is not None:
            _append_readiness_failure(self.paths.log_file, service, probe_timeout, last_probe)
        raise RuntimeFailure("SERVICE_READINESS_TIMEOUT", "A service did not become ready.", service)

    def _supervise(self) -> None:
        endpoints = {
            "fuseki": f"http://127.0.0.1:{PORTS['fuseki']}/projecta/query?query=ASK%7B%7D",
            "semanticCore": f"http://127.0.0.1:{PORTS['semanticCore']}/health/ready",
            "api": f"http://127.0.0.1:{PORTS['api']}/health/ready",
        }
        while True:
            if self._consume_stop_request():
                _append_safe_log(self.paths.log_file, "stop-requested")
                return
            for service, url in endpoints.items():
                self.host.check_alive(service)
                probe_timeout = READINESS_PROBE_TIMEOUTS.get(service, HTTP_PROBE_TIMEOUT_SECONDS)
                probe = _http_probe(url, timeout=probe_timeout, capture_error_body=service == "api")
                if probe.status_code != 200:
                    _append_readiness_failure(self.paths.log_file, service, probe_timeout, probe)
                    raise RuntimeFailure("SERVICE_BECAME_UNREADY", "A service stopped reporting readiness.", service)
            self.host.check_alive("postgres")
            if self._postgres_probe() != 0:
                raise RuntimeFailure("SERVICE_BECAME_UNREADY", "PostgreSQL stopped reporting readiness.", "postgres")
            self._write_status("ready")
            time.sleep(2)

    def _postgres_probe(self) -> int:
        binary = self.paths.runtime / "postgresql" / "bin" / "pg_isready.exe"
        try:
            return subprocess.run(
                [str(binary), "--host=127.0.0.1", f"--port={PORTS['postgres']}", "--username=projecta", "--dbname=postgres"],
                env=self._environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            ).returncode
        except (OSError, subprocess.TimeoutExpired):
            return 1

    def _consume_stop_request(self) -> bool:
        try:
            value = load_json(self.paths.stop_file, "STOP_REQUEST_INVALID")
        except RuntimeFailure:
            return False
        if value.get("runtimeId") != self.runtime_id:
            return False
        self.paths.stop_file.unlink(missing_ok=True)
        return True

    def _write_status(self, state: str, *, failure: RuntimeFailure | None = None) -> None:
        services = {
            name: "running" if child.process.poll() is None else "stopped"
            for name, child in self.host.processes.items()
        }
        document: dict[str, object] = {
            "formatVersion": 1,
            "runtimeId": self.runtime_id,
            "managerPid": os.getpid(),
            "state": state,
            "updatedAt": _utc_now(),
            "url": f"http://127.0.0.1:{PORTS['api']}/" if state == "ready" else None,
            "services": services,
            "processes": {name: child.process.pid for name, child in self.host.processes.items()},
        }
        if failure is not None:
            document["failureCode"] = failure.code
            if failure.service:
                document["failedService"] = failure.service
        atomic_json(self.paths.status_file, document)

    def _stop_postgres(self) -> None:
        child = self.host.processes.get("postgres")
        if child is None:
            return
        if child.process.poll() is not None:
            del self.host.processes["postgres"]
            self.host._job_assigned.pop("postgres", None)
            if not self.host.processes:
                self.host.close_job()
            return
        pg_ctl = self.paths.runtime / "postgresql" / "bin" / "pg_ctl.exe"
        environment = self._environment()
        self.host.run_task(
            "postgres",
            [str(pg_ctl), "--pgdata", str(self.paths.data / "postgres"), "--mode=fast", "--wait", "--timeout=60", "stop"],
            environment,
            self.paths.runtime / "postgresql",
            timeout=75,
        )
        try:
            result = child.process.wait(timeout=15)
        except subprocess.TimeoutExpired as error:
            raise RuntimeFailure("GRACEFUL_STOP_TIMEOUT", "PostgreSQL did not exit after shutdown was requested.", "postgres") from error
        del self.host.processes["postgres"]
        self.host._job_assigned.pop("postgres", None)
        if not self.host.processes:
            self.host.close_job()
        if result != 0:
            raise RuntimeFailure("GRACEFUL_STOP_FAILED", "PostgreSQL exited with an error during shutdown.", "postgres")

    def _stop_owned_processes(self) -> RuntimeFailure | None:
        try:
            self.host.stop_all(("api", "semanticCore", "fuseki", "postgres"), self._stop_postgres)
            return None
        except RuntimeFailure as error:
            _append_safe_log(self.paths.log_file, "graceful-stop-failed", code=error.code, service=error.service)
            return error

    def _wait_for_graceful_stop_retry(self) -> None:
        while self.host.alive_names():
            self._write_status("shutdown-failed", failure=self._failure)
            if self._consume_stop_request():
                stop_error = self._stop_owned_processes()
                if stop_error is None:
                    return
                self._failure = stop_error
            time.sleep(0.5)

    def _open_browser(self) -> None:
        if not self.open_browser:
            return
        import webbrowser

        try:
            if not webbrowser.open(f"http://127.0.0.1:{PORTS['api']}/", new=2):
                _append_safe_log(self.paths.log_file, "browser-open-failed")
                print("Projecta Local is ready; open http://127.0.0.1:18732/ in your browser.")
        except OSError:
            _append_safe_log(self.paths.log_file, "browser-open-failed")
            print("Projecta Local is ready; open http://127.0.0.1:18732/ in your browser.")


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)
    return bool(is_junction(path)) if is_junction is not None else False


def _remove_directory_tree(path: Path) -> None:
    """Remove a directory tree without following reparse points."""
    if _is_reparse_point(path):
        raise RuntimeFailure("LOCAL_PATH_UNSAFE", "A local data path contains a link or junction.")
    if path.is_symlink():
        raise RuntimeFailure("LOCAL_PATH_UNSAFE", "A local data path contains a link or junction.")
    for child in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
        if _is_reparse_point(child) or child.is_symlink():
            raise RuntimeFailure("LOCAL_PATH_UNSAFE", "A local data path contains a link or junction.")
        if child.is_dir() and not child.is_symlink():
            _remove_directory_tree(child)
        else:
            child.unlink()
    path.rmdir()


def _move_state(source: Path, destination: Path) -> None:
    """Move a file or directory without replacing an existing directory in place.

    Windows refuses ``os.replace`` when the destination is an existing directory
    (``PermissionError: [WinError 5]``), and replacing a live data directory would
    destroy the rollback source. Callers stage into an empty location, then move.
    """
    if _is_reparse_point(source):
        raise RuntimeFailure("LOCAL_PATH_UNSAFE", "A local data path contains a link or junction.")
    if destination.exists():
        if source.is_dir() and not source.is_symlink() and destination.is_dir() and not destination.is_symlink():
            _remove_directory_tree(destination)
        else:
            destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(source, destination)
    except OSError:
        # Cross-volume or locked-target fallback: copy then remove the source.
        if source.is_dir() and not source.is_symlink():
            _copy_state(source, destination)
            _remove_directory_tree(source)
        else:
            shutil.copyfile(source, destination)
            source.unlink()


def _copy_state(source: Path, destination: Path) -> None:
    if _is_reparse_point(source):
        raise RuntimeFailure("BACKUP_REPARSE_POINT", "The state contains a link or junction and was not copied.")
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=False)
        for child in sorted(source.iterdir(), key=lambda path: path.name.casefold()):
            _copy_state(child, destination / child.name)
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    else:
        raise RuntimeFailure("BACKUP_STATE_INVALID", "The state contains an unsupported file type.")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot_entries(items_root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []

    def walk(path: Path) -> None:
        if _is_reparse_point(path):
            raise RuntimeFailure("BACKUP_REPARSE_POINT", "The state contains a link or junction and was not copied.")
        relative = path.relative_to(items_root).as_posix()
        if path.is_dir():
            entries.append({"path": relative, "kind": "directory"})
            for child in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
                walk(child)
        elif path.is_file():
            entries.append({"path": relative, "kind": "file", "size": path.stat().st_size, "sha256": _file_sha256(path)})
        else:
            raise RuntimeFailure("BACKUP_STATE_INVALID", "The state contains an unsupported file type.")

    for child in sorted(items_root.iterdir(), key=lambda path: path.name.casefold()):
        walk(child)
    return entries


def _expected_manifest_roots(entries: Sequence[Mapping[str, object]]) -> set[str]:
    roots: set[str] = set()
    for entry in entries:
        relative = entry.get("path")
        if not isinstance(relative, str) or not _is_safe_relative_path(relative):
            raise RuntimeFailure("BACKUP_MANIFEST_INVALID", "The backup contains an unsafe path.")
        roots.add(PurePosixPath(relative).parts[0])
    return roots


class BackupManager:
    def __init__(self, paths: ProjectaPaths) -> None:
        self.paths = paths

    def create(self) -> str:
        with instance_lock(self.paths.lock_file):
            self._require_quiescent()
            runtime_manifest = load_runtime_manifest(self.paths)
            self._require_plain_state_path(self.paths.local_config)
            load_json(self.paths.local_config, "LOCAL_PROJECT_CONFIGURATION_INVALID")
            self._require_plain_state_path(self.paths.protected_secrets)
            if not self.paths.protected_secrets.is_file():
                raise RuntimeFailure("SECRET_STORE_RECOVERY_REQUIRED", "The local DPAPI secret file is missing.")
            for relative in SNAPSHOT_PATHS:
                source = self.paths.data_root / Path(*relative.parts)
                self._require_plain_state_path(source)
                if not source.exists():
                    raise RuntimeFailure("BACKUP_STATE_INCOMPLETE", "A required local data component is missing.")
            backup_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{uuid.uuid4().hex[:8]}"
            temporary = self.paths.backups / f".{backup_id}.incomplete"
            final = self.paths.backups / backup_id
            self._require_plain_state_path(temporary)
            if final.exists() or temporary.exists():
                raise RuntimeFailure("BACKUP_ID_CONFLICT", "A backup identifier already exists.")
            temporary.mkdir(parents=True)
            items = temporary / "items"
            items.mkdir()
            try:
                for relative in SNAPSHOT_PATHS:
                    source = self.paths.data_root / Path(*relative.parts)
                    _copy_state(source, items / Path(*relative.parts))
                entries = _snapshot_entries(items)
                roots = _expected_manifest_roots(entries)
                if roots != {relative.parts[0] for relative in SNAPSHOT_PATHS}:
                    raise RuntimeFailure("BACKUP_STATE_INCOMPLETE", "The snapshot does not contain every required state root.")
                atomic_json(
                    temporary / "manifest.json",
                    {
                        "formatVersion": 1,
                        "backupId": backup_id,
                        "createdAt": _utc_now(),
                        "projectaVersion": runtime_manifest["projectaVersion"],
                        "runtimeVersions": runtime_manifest["runtimeVersions"],
                        "entries": entries,
                    },
                )
                if final.exists():
                    raise RuntimeFailure("BACKUP_ID_CONFLICT", "A backup identifier already exists.")
                _move_state(temporary, final)
            except BaseException:
                if temporary.exists():
                    shutil.rmtree(temporary)
                raise
            return backup_id

    def restore(self, backup_id: str) -> Path:
        if not BACKUP_ID_PATTERN.fullmatch(backup_id):
            raise RuntimeFailure("BACKUP_ID_INVALID", "The selected backup identifier is invalid.")
        with instance_lock(self.paths.lock_file):
            self._require_quiescent()
            current_manifest = load_runtime_manifest(self.paths)
            backup_root = self.paths.backups / backup_id
            self._require_plain_state_path(backup_root)
            self._require_plain_state_path(backup_root / "manifest.json")
            manifest = load_json(backup_root / "manifest.json", "BACKUP_MANIFEST_INVALID")
            if manifest.get("formatVersion") != 1 or manifest.get("backupId") != backup_id:
                raise RuntimeFailure("BACKUP_MANIFEST_INVALID", "The selected backup manifest is invalid.")
            if (
                manifest.get("projectaVersion") != current_manifest.get("projectaVersion")
                or manifest.get("runtimeVersions") != current_manifest.get("runtimeVersions")
            ):
                raise RuntimeFailure("BACKUP_VERSION_MISMATCH", "Restore requires the exact application and runtime versions used to create the backup.")
            raw_entries = manifest.get("entries")
            if not isinstance(raw_entries, list) or any(not isinstance(entry, dict) for entry in raw_entries):
                raise RuntimeFailure("BACKUP_MANIFEST_INVALID", "The selected backup manifest is invalid.")
            entries = raw_entries
            allowed_roots = {relative.parts[0] for relative in SNAPSHOT_PATHS}
            if _expected_manifest_roots(entries) != allowed_roots:
                raise RuntimeFailure("BACKUP_MANIFEST_INVALID", "The selected backup contains unsupported state paths.")
            self._require_plain_state_path(backup_root / "items")
            self._verify_entries(backup_root / "items", entries)
            stage_id = uuid.uuid4().hex
            stage_root = self.paths.recovery / f"restore-stage-{stage_id}"
            previous_root = self.paths.recovery / f"pre-restore-{backup_id}-{stage_id[:8]}"
            failed_root = self.paths.recovery / f"failed-restore-{backup_id}-{stage_id[:8]}"
            self._require_plain_state_path(stage_root)
            self._require_plain_state_path(previous_root)
            self._require_plain_state_path(failed_root)
            stage_root.mkdir(parents=True)
            # Two-phase swap: every live entry moves to previous_root first, and only
            # then do staged entries move into place. A failure in phase one leaves
            # untouched live entries plus previous_root intact; a failure in phase two
            # rolls the previous entries back, so the live tree is never a mixture of
            # old and restored state.
            moved_old: list[PurePosixPath] = []
            moved_new: list[PurePosixPath] = []
            try:
                for relative in SNAPSHOT_PATHS:
                    _copy_state(backup_root / "items" / Path(*relative.parts), stage_root / Path(*relative.parts))
                previous_root.mkdir(parents=True)
                for relative in SNAPSHOT_PATHS:
                    target = self.paths.data_root / Path(*relative.parts)
                    self._require_plain_state_path(target)
                    old = previous_root / Path(*relative.parts)
                    if target.exists() or target.is_symlink():
                        old.parent.mkdir(parents=True, exist_ok=True)
                        _move_state(target, old)
                        moved_old.append(relative)
                for relative in SNAPSHOT_PATHS:
                    target = self.paths.data_root / Path(*relative.parts)
                    staged = stage_root / Path(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    _move_state(staged, target)
                    moved_new.append(relative)
            except BaseException as error:
                if isinstance(error, RuntimeFailure) and error.code in {
                    "LOCAL_PATH_UNSAFE",
                    "BACKUP_REPARSE_POINT",
                    "BACKUP_STATE_INVALID",
                }:
                    raise
                failed_root.mkdir(parents=True, exist_ok=True)
                for relative in reversed(moved_new):
                    current = self.paths.data_root / Path(*relative.parts)
                    preserved = failed_root / Path(*relative.parts)
                    if current.exists() or current.is_symlink():
                        preserved.parent.mkdir(parents=True, exist_ok=True)
                        _move_state(current, preserved)
                for relative in reversed(moved_old):
                    old = previous_root / Path(*relative.parts)
                    target = self.paths.data_root / Path(*relative.parts)
                    if old.exists() or old.is_symlink():
                        if target.exists() or target.is_symlink():
                            if target.is_dir() and not target.is_symlink():
                                _remove_directory_tree(target)
                            else:
                                target.unlink()
                        target.parent.mkdir(parents=True, exist_ok=True)
                        _move_state(old, target)
                # Preserve staged entries that were never placed (a placement failure
                # leaves them in stage_root, which the finally block deletes). The
                # sets are disjoint from moved_new, so no preserved path collides.
                for relative in SNAPSHOT_PATHS:
                    if relative in moved_new:
                        continue
                    staged = stage_root / Path(*relative.parts)
                    if not staged.exists() and not staged.is_symlink():
                        continue
                    preserved = failed_root / Path(*relative.parts)
                    if preserved.exists() or preserved.is_symlink():
                        continue
                    preserved.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        _move_state(staged, preserved)
                    except OSError:
                        pass
                raise RuntimeFailure("BACKUP_RESTORE_ROLLED_BACK", "Restore failed; the pre-restore state was put back and the attempted files were preserved.") from error
            finally:
                if stage_root.exists():
                    shutil.rmtree(stage_root)
            return previous_root

    def _require_plain_state_path(self, path: Path) -> None:
        base = self.paths.data_root
        try:
            path.relative_to(base)
        except ValueError as error:
            raise RuntimeFailure("LOCAL_PATH_UNSAFE", "A local data path escaped the per-user state directory.") from error
        candidate = path
        while candidate != base.parent:
            if _is_reparse_point(candidate):
                raise RuntimeFailure("LOCAL_PATH_UNSAFE", "A local data path contains a link or junction.")
            candidate = candidate.parent

    def _require_quiescent(self) -> None:
        for service, port in PORTS.items():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.2)
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeFailure(
                        "RUNTIME_MUST_BE_STOPPED",
                        "Stop Projecta Local and any service using its local ports before backup or restore.",
                        service,
                    )

    def _verify_entries(self, items_root: Path, entries: Sequence[Mapping[str, object]]) -> None:
        if _is_reparse_point(items_root) or not items_root.is_dir():
            raise RuntimeFailure("BACKUP_REPARSE_POINT", "The selected backup contains a link or junction.")
        expected: dict[str, Mapping[str, object]] = {}
        for entry in entries:
            relative = entry.get("path")
            kind = entry.get("kind")
            if not isinstance(relative, str) or not _is_safe_relative_path(relative) or relative in expected:
                raise RuntimeFailure("BACKUP_MANIFEST_INVALID", "The selected backup manifest contains invalid paths.")
            if kind == "directory":
                if set(entry) != {"path", "kind"}:
                    raise RuntimeFailure("BACKUP_MANIFEST_INVALID", "The selected backup manifest contains invalid entries.")
            elif kind == "file":
                size = entry.get("size")
                digest = entry.get("sha256")
                if (
                    set(entry) != {"path", "kind", "size", "sha256"}
                    or type(size) is not int
                    or size < 0
                    or not isinstance(digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)
                ):
                    raise RuntimeFailure("BACKUP_MANIFEST_INVALID", "The selected backup manifest contains invalid entries.")
            else:
                raise RuntimeFailure("BACKUP_MANIFEST_INVALID", "The selected backup contains an unsupported entry.")
            expected[relative] = entry
        actual = {entry["path"]: entry for entry in _snapshot_entries(items_root)}
        if actual != expected:
            raise RuntimeFailure("BACKUP_CONTENT_INVALID", "The selected backup is incomplete or changed.")
        if not all((items_root / Path(*relative.parts)).exists() for relative in SNAPSHOT_PATHS):
            raise RuntimeFailure("BACKUP_CONTENT_INVALID", "The selected backup is missing a required state component.")


def _create_shortcuts(paths: ProjectaPaths, *, package_root: Path | None = None) -> None:
    if os.name != "nt":
        raise RuntimeFailure("PACKAGED_LAUNCHER_REQUIRED", "Install requires a packaged Projecta application.")
    if not getattr(sys, "frozen", False) or _is_staged_runtime():
        return
    launch_root = package_root or paths.package_root
    program = str(
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    working_directory = str(launch_root)
    arguments = (
        '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "'
        f'{launch_root / "ProjectaStart.ps1"}"'
    )
    shortcut_script = r"""
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$programs = Join-Path ([Environment]::GetFolderPath('Programs')) 'Projecta'
New-Item -ItemType Directory -Path $programs -Force | Out-Null
foreach ($oldName in @('Projecta Local Start.lnk', 'Projecta Local Stop.lnk', 'Projecta Local Status.lnk')) {
    Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath('Programs')) $oldName) -Force -ErrorAction SilentlyContinue
}
$shortcut = $shell.CreateShortcut((Join-Path $programs 'Projecta.lnk'))
$shortcut.Arguments = $env:PROJECTA_SHORTCUT_ARGUMENTS
$shortcut.IconLocation = $env:PROJECTA_SHORTCUT_ICON
$shortcut.TargetPath = $env:PROJECTA_SHORTCUT_TARGET
$shortcut.WorkingDirectory = $env:PROJECTA_SHORTCUT_WORKING_DIRECTORY
$shortcut.Description = 'Projecta 0.7.0 unsigned pre-release test application'
$shortcut.Save()
"""
    encoded = base64.b64encode(shortcut_script.encode("utf-16le")).decode("ascii")
    environment = os.environ.copy()
    environment["PROJECTA_SHORTCUT_TARGET"] = program
    environment["PROJECTA_SHORTCUT_ARGUMENTS"] = arguments
    environment["PROJECTA_SHORTCUT_ICON"] = str(launch_root / "Projecta.exe")
    environment["PROJECTA_SHORTCUT_WORKING_DIRECTORY"] = working_directory
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeFailure("SHORTCUT_CREATION_FAILED", "The per-user Start Menu shortcuts could not be created.") from error
    if result.returncode:
        raise RuntimeFailure("SHORTCUT_CREATION_FAILED", "The per-user Start Menu shortcuts could not be created.")


def _copy_package_to_version(
    source: Path,
    programs_root: Path,
    version: str,
    data_root: Path,
) -> Path:
    destination = programs_root / version
    source_manifest = source / "runtime-manifest.json"
    if source.resolve() == destination.resolve():
        return destination
    if destination.exists():
        installed = ProjectaPaths(destination, data_root)
        load_runtime_manifest(installed, expected_project_version=version)
        if (destination / "runtime-manifest.json").read_bytes() != source_manifest.read_bytes():
            raise RuntimeFailure("INSTALL_VERSION_CONFLICT", "A different package with this version is already installed.")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{version}.staging-{uuid.uuid4().hex}"
    try:
        shutil.copytree(source, staging)
        load_runtime_manifest(ProjectaPaths(staging, data_root), expected_project_version=version)
        os.rename(staging, destination)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def _local_programs_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeFailure("LOCAL_DATA_ROOT_MISSING", "Windows did not provide a per-user local data directory.")
    return Path(local_app_data) / "Programs" / "Projecta"


def install(paths: ProjectaPaths, *, workspace_name: str | None = None) -> bool:
    _require_windows_11_x64()
    manifest = load_runtime_manifest(paths)
    _require_package_distribution(manifest)
    if getattr(sys, "frozen", False) and not _is_staged_runtime():
        destination = _copy_package_to_version(
            paths.package_root,
            _local_programs_root(),
            APP_VERSION,
            paths.data_root,
        )
        paths = ProjectaPaths(destination, paths.data_root)
        manifest = load_runtime_manifest(paths)
    paths.ensure_user_directories()
    has_installation = paths.installation_config.exists()
    if has_installation:
        current = load_json(paths.installation_config, "LOCAL_INSTALLATION_INVALID")
        if (
            current.get("runtimeVersions") != manifest["runtimeVersions"]
            or current.get("dataContractVersion", DATA_CONTRACT_VERSION) != manifest["dataContractVersion"]
        ):
            raise RuntimeFailure("UPDATE_RECOVERY_REQUIRED", "The installed data version requires an approved migration.")
    if paths.protected_secrets.is_file():
        unprotect_runtime_secrets(paths.protected_secrets)
    elif has_installation:
        raise RuntimeFailure("SECRET_STORE_RECOVERY_REQUIRED", "The installed DPAPI secret file is missing; no replacement was generated.")
    else:
        protect_runtime_secrets(paths.protected_secrets, generate_runtime_secrets())
    if not paths.local_config.is_file():
        provision_first_run_workspace(paths.local_config, display_name=workspace_name or FIRST_RUN_DISPLAY_NAME)
    current = load_json(paths.installation_config, "LOCAL_INSTALLATION_INVALID") if has_installation else {}
    atomic_json(
        paths.installation_config,
        {
            "formatVersion": 1,
            "projectaVersion": manifest["projectaVersion"],
            "runtimeVersions": manifest["runtimeVersions"],
            "dataContractVersion": manifest["dataContractVersion"],
            "installedAt": current.get("installedAt") or _utc_now(),
        },
    )
    _create_shortcuts(paths)
    return manifest.get("releaseEligible") is True


def _verify_update_package(
    package: Path,
    *,
    trusted_public_key: bytes | None = None,
) -> dict[str, object]:
    if not package.is_dir() or _is_reparse_point(package):
        raise RuntimeFailure("UPDATE_PACKAGE_INVALID", "The update package directory is invalid.")
    manifest_path = package / "runtime-manifest.json"
    if _is_reparse_point(manifest_path):
        raise RuntimeFailure("UPDATE_PACKAGE_INVALID", "The update package manifest is unsafe.")
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeFailure("UPDATE_PACKAGE_INVALID", "The update package manifest is missing or invalid.") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("formatVersion") != 1
        or manifest.get("releaseEligible") is not True
        or manifest.get("distributionChannel") != "signed-release"
        or "unsignedPreReleaseException" in manifest
        or manifest.get("signatureAlgorithm") != "Ed25519"
        or type(manifest.get("dataContractVersion")) is not int
        or manifest["dataContractVersion"] < 1
    ):
        raise RuntimeFailure("UPDATE_PACKAGE_INVALID", "The update package manifest is not supported.")
    _version_tuple(manifest.get("projectaVersion"))
    signature = package / "runtime-manifest.sig"
    if not signature.is_file():
        raise RuntimeFailure(
            "UPDATE_SIGNATURE_REQUIRED",
            "The update package has no owner release signature; refusing to apply an unsigned update.",
        )
    public_key = trusted_public_key if trusted_public_key is not None else _release_public_key()
    _verify_ed25519_signature(manifest_bytes, signature, public_key)
    _verify_package_inventory(package, manifest, error_code="UPDATE_PACKAGE_CONTENT_INVALID")
    _validate_vc_runtime_prerequisite(
        package,
        manifest,
        error_code="UPDATE_PACKAGE_INVALID",
    )
    required = {
        "ProjectaLocal.exe",
        "Projecta.exe",
        "runtime/python/python.exe",
        "runtime/python/python312._pth",
        "runtime/python/uv.lock",
        "runtime/python/wheel-requirements.txt",
        "runtime/python/wheel-manifest.json",
        "runtime/java/bin/java.exe",
        "runtime/postgresql/bin/initdb.exe",
        "runtime/postgresql/bin/postgres.exe",
        "runtime/postgresql/bin/pg_ctl.exe",
        "runtime/postgresql/bin/createdb.exe",
        "runtime/postgresql/bin/pg_isready.exe",
        "runtime/postgresql/bin/psql.exe",
        "projecta/api/src/projecta_api/main.py",
        "projecta/semantic-core/classes/org/projecta/semanticcore/SemanticCoreApplication.class",
        "projecta/semantic-core/classes/org/projecta/semanticcore/LocalFusekiServer.class",
        "projecta/semantic-core/runtime-manifest.json",
        "projecta/fuseki-config.template.ttl",
        "projecta/ontology/core.ttl",
        "projecta/ontology/runtime-manifest.json",
        "projecta/web/index.html",
        "projecta/web/runtime-manifest.json",
        "THIRD-PARTY-NOTICES.md",
        "PROJECTA-LICENSE.txt",
        "runtime/native-dependency-manifest.json",
        "projecta/semantic-core/java-third-party-notices.json",
        "runtime/postgresql/server_license.txt",
        "runtime/postgresql/commandlinetools_3rd_party_licenses.txt",
        "ProjectaStart.ps1",
        "runtime/vc-runtime-policy.json",
        "runtime/vc_runtime_prerequisite.ps1",
    }
    listed = {entry["path"] for entry in manifest["files"]}  # type: ignore[index]
    notice_files = manifest.get("noticeFiles")
    if (
        not isinstance(notice_files, list)
        or not notice_files
        or any(
            not isinstance(notice, str)
            or not _is_safe_relative_path(notice)
            or notice not in listed
            for notice in notice_files
        )
        or len(set(notice_files)) != len(notice_files)
    ):
        raise RuntimeFailure("UPDATE_PACKAGE_INVALID", "The update package notice index is missing or invalid.")
    if not required.issubset(listed):
        raise RuntimeFailure("UPDATE_PACKAGE_INVALID", "The update package omits required runtime or application files.")
    return manifest


def apply_update(paths: ProjectaPaths, package: Path) -> None:
    """Verify and install a signed, data-contract-compatible package side by side."""
    _require_windows_11_x64()
    if runtime_is_active(paths):
        raise RuntimeFailure("RUNTIME_MUST_BE_STOPPED", "Stop Projecta Local before applying an update.")
    manifest = _verify_update_package(package)
    current = load_runtime_manifest(paths)
    if _version_tuple(manifest.get("projectaVersion")) <= _version_tuple(current.get("projectaVersion")):
        raise RuntimeFailure("UPDATE_VERSION_NOT_NEWER", "The update package is not newer than the installed version.")
    if (
        manifest.get("runtimeVersions") != current.get("runtimeVersions")
        or manifest.get("dataContractVersion") != current.get("dataContractVersion")
    ):
        raise RuntimeFailure(
            "UPDATE_RECOVERY_REQUIRED",
            "The update package changes the runtime or data contract; a reviewed migration is required.",
        )
    installation = load_json(paths.installation_config, "LOCAL_INSTALLATION_INVALID")
    if (
        installation.get("runtimeVersions") != current.get("runtimeVersions")
        or installation.get("dataContractVersion", DATA_CONTRACT_VERSION)
        != current.get("dataContractVersion")
    ):
        raise RuntimeFailure("UPDATE_RECOVERY_REQUIRED", "The installed data does not match its recorded contract.")
    destination = _copy_package_to_version(
        package,
        _local_programs_root(),
        str(manifest["projectaVersion"]),
        paths.data_root,
    )
    atomic_json(
        paths.installation_config,
        {
            "formatVersion": 1,
            "projectaVersion": manifest["projectaVersion"],
            "runtimeVersions": manifest["runtimeVersions"],
            "dataContractVersion": manifest["dataContractVersion"],
            "installedAt": installation.get("installedAt") or _utc_now(),
        },
    )
    _create_shortcuts(paths, package_root=destination)
    print(f"Signed update {manifest['projectaVersion']} verified and installed; local data was retained.")


def request_stop(paths: ProjectaPaths) -> None:
    if not runtime_is_active(paths):
        print("Projecta Local is stopped; its data remains in the per-user data directory.")
        return
    try:
        status = load_json(paths.status_file, "RUNTIME_STATUS_INVALID")
    except RuntimeFailure as error:
        raise RuntimeFailure("RUNTIME_STATUS_INVALID", "The active manager has not published a readable status file yet.") from error
    runtime_id = status.get("runtimeId")
    if not isinstance(runtime_id, str) or not runtime_id:
        raise RuntimeFailure("RUNTIME_STATUS_INVALID", "The active manager status is invalid.")
    atomic_json(paths.stop_file, {"runtimeId": runtime_id, "requestedAt": _utc_now()})
    print("Graceful stop requested. The running launcher will stop dependent services in reverse order.")


def show_status(paths: ProjectaPaths) -> None:
    active = runtime_is_active(paths)
    try:
        status = load_json(paths.status_file, "RUNTIME_STATUS_INVALID")
    except RuntimeFailure:
        status = {"state": "stopped", "services": {}}
    state = status.get("state") if active else "stopped"
    print(f"Projecta Local: {state}")
    if state == "ready":
        print(f"Browser: http://127.0.0.1:{PORTS['api']}/")
    failure_code = status.get("failureCode")
    if isinstance(failure_code, str):
        print(f"Diagnostic code: {failure_code}")
    if not paths.local_config.is_file():
        print("First-run workspace: not provisioned yet; start provisions the approved first-run workspace on a fresh data directory.")
    services = status.get("services")
    if isinstance(services, dict):
        for name in sorted(services):
            value = services[name]
            if isinstance(name, str) and isinstance(value, str):
                print(f"  {name}: {value if active else 'stopped'}")


def _create_snapshot(paths: ProjectaPaths) -> str:
    return BackupManager(paths).create()


def _restore_snapshot(paths: ProjectaPaths, backup_id: str) -> Path:
    return BackupManager(paths).restore(backup_id)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Projecta Local per-user service launcher")
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install", help="Install this package for the current Windows user")
    install_parser.add_argument("--workspace-name", help=argparse.SUPPRESS)
    start = commands.add_parser("start", help="Start and supervise the local Projecta services")
    start.add_argument("--no-browser", action="store_true", help=argparse.SUPPRESS)
    commands.add_parser("stop", help="Request reverse-order graceful shutdown")
    commands.add_parser("status", help="Show local service readiness without changing data")
    backup = commands.add_parser("backup", help="Create or restore a stopped-runtime state snapshot")
    backup_commands = backup.add_subparsers(dest="backup_command", required=True)
    backup_commands.add_parser("create", help="Create a quiesced, hash-verified local snapshot")
    restore = backup_commands.add_parser("restore", help="Restore an exact-version snapshot")
    restore.add_argument("backup_id")
    restore.add_argument("--confirm", action="store_true", help="Confirm replacement after rollback-copy retention")
    update = commands.add_parser("update", help="Apply a user-approved signed update package")
    update.add_argument("package", help="Directory containing runtime-manifest.json and its owner signature")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        paths = ProjectaPaths.discover()
        if args.command == "install":
            fresh_install = not paths.local_config.is_file()
            release_eligible = install(paths, workspace_name=args.workspace_name)
            if not release_eligible:
                print("Projecta 0.7.0 unsigned pre-release test installed. Publisher identity is unverified; signed updates remain required.")
            elif fresh_install:
                print("Projecta is installed; the selected first-run workspace was provisioned.")
            else:
                print("Projecta is installed for this Windows user.")
            return 0
        if args.command == "start":
            return RuntimeManager(paths, open_browser=not args.no_browser).start()
        if args.command == "stop":
            request_stop(paths)
            return 0
        if args.command == "update":
            apply_update(paths, Path(str(args.package)))
            return 0
        if args.command == "status":
            show_status(paths)
            return 0
        if args.command == "backup" and args.backup_command == "create":
            backup_id = _create_snapshot(paths)
            print(f"Snapshot created: {backup_id}")
            return 0
        if args.command == "backup" and args.backup_command == "restore":
            if not args.confirm:
                raise RuntimeFailure("RESTORE_CONFIRMATION_REQUIRED", "Restore changes local state; rerun with --confirm after reviewing the backup ID.")
            previous = _restore_snapshot(paths, args.backup_id)
            print(f"Snapshot restored. The pre-restore state was retained at: {previous}")
            return 0
        raise RuntimeFailure("COMMAND_INVALID", "The requested Projecta Local command is invalid.")
    except RuntimeFailure as error:
        print(f"Projecta Local: {error.message} [{error.code}]", file=sys.stderr)
        return 2
    except Exception:
        print("Projecta Local: the command failed safely [RUNTIME_INTERNAL_ERROR]", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
