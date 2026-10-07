from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_launcher_path = Path(__file__).resolve().parents[1] / "projecta_local.py"
_launcher_spec = importlib.util.spec_from_file_location("projecta_local_launcher", _launcher_path)
if _launcher_spec is None or _launcher_spec.loader is None:
    raise RuntimeError("could not load the per-user launcher module")
launcher = importlib.util.module_from_spec(_launcher_spec)
sys.modules[_launcher_spec.name] = launcher
_launcher_spec.loader.exec_module(launcher)


def _signed_update_package(
    package: Path,
) -> tuple[bytes, bytes, Path]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    required = (
        "ProjectaLocal.exe",
        "Projecta.exe",
        "ProjectaStart.ps1",
        "runtime/vc-runtime-policy.json",
        "runtime/vc_runtime_prerequisite.ps1",
        "runtime/python/python.exe",
        "runtime/python/python312._pth",
        "runtime/python/uv.lock",
        "runtime/python/wheel-requirements.txt",
        "runtime/python/wheel-manifest.json",
        "runtime/native-dependency-manifest.json",
        "runtime/java/bin/java.exe",
        "runtime/postgresql/bin/initdb.exe",
        "runtime/postgresql/bin/postgres.exe",
        "runtime/postgresql/bin/pg_ctl.exe",
        "runtime/postgresql/bin/createdb.exe",
        "runtime/postgresql/bin/pg_isready.exe",
        "runtime/postgresql/bin/psql.exe",
        "runtime/postgresql/server_license.txt",
        "runtime/postgresql/commandlinetools_3rd_party_licenses.txt",
        "projecta/api/src/projecta_api/main.py",
        "projecta/semantic-core/classes/org/projecta/semanticcore/SemanticCoreApplication.class",
        "projecta/semantic-core/classes/org/projecta/semanticcore/LocalFusekiServer.class",
        "projecta/semantic-core/runtime-manifest.json",
        "projecta/semantic-core/java-third-party-notices.json",
        "projecta/fuseki-config.template.ttl",
        "projecta/ontology/core.ttl",
        "projecta/ontology/runtime-manifest.json",
        "projecta/web/index.html",
        "projecta/web/runtime-manifest.json",
        "THIRD-PARTY-NOTICES.md",
        "PROJECTA-LICENSE.txt",
    )
    for index, relative in enumerate(required):
        path = package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"test payload {index}\n".encode())
    policy_path = package / "runtime" / "vc-runtime-policy.json"
    policy_path.write_text(json.dumps(launcher.VC_RUNTIME_PREREQUISITE), encoding="utf-8")
    files = [
        {
            "path": relative,
            "size": (package / relative).stat().st_size,
            "sha256": hashlib.sha256((package / relative).read_bytes()).hexdigest(),
        }
        for relative in required
    ]
    manifest_bytes = (
        json.dumps(
            {
                "formatVersion": 1,
                "projectaVersion": "0.7.0",
                "dataContractVersion": 1,
                "releaseEligible": True,
                "distributionChannel": "signed-release",
                "signatureAlgorithm": "Ed25519",
                "runtimeVersions": dict(launcher.RUNTIME_VERSIONS),
                "vcRuntimePrerequisite": dict(launcher.VC_RUNTIME_PREREQUISITE),
                "noticeFiles": ["THIRD-PARTY-NOTICES.md"],
                "files": files,
            },
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    (package / "runtime-manifest.json").write_bytes(manifest_bytes)
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    signature = base64.b64encode(private_key.sign(manifest_bytes))
    signature_path = package / "runtime-manifest.sig"
    signature_path.write_bytes(signature)
    return public_key, manifest_bytes, package / required[1]


@pytest.fixture
def local_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> launcher.ProjectaPaths:
    paths = launcher.ProjectaPaths(tmp_path / "package", tmp_path / "user-data")
    paths.package_root.mkdir(parents=True)
    paths.ensure_user_directories()
    (paths.data / "postgres" / "database.bin").write_bytes(b"original database")
    (paths.data / "fuseki" / "store.bin").write_bytes(b"original graph store")
    (paths.data / "sqlite" / "catalog.db").write_bytes(b"original catalog")
    (paths.data / "evidence" / "record.json").write_text("original evidence", encoding="utf-8")
    paths.local_config.write_text("{}", encoding="utf-8")
    paths.installation_config.write_text("{}", encoding="utf-8")
    paths.protected_secrets.write_bytes(b"test protected-secret blob")
    monkeypatch.setattr(
        launcher,
        "load_runtime_manifest",
        lambda _: {"projectaVersion": launcher.APP_VERSION, "runtimeVersions": dict(launcher.RUNTIME_VERSIONS)},
    )
    monkeypatch.setattr(launcher, "PORTS", {"unused": 0})
    return paths

def test_api_readiness_probe_accepts_nested_dependency_latency() -> None:
    class DelayedReadyHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            time.sleep(2.2)
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), DelayedReadyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        probe = launcher._http_probe(
            f"http://127.0.0.1:{server.server_port}/health/ready",
            timeout=launcher.API_READINESS_TIMEOUT_SECONDS,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert probe.status_code == 200
    assert probe.elapsed_ms >= 2_000


def test_semantic_core_probe_accepts_nested_fuseki_latency() -> None:
    class DelayedReadyHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            time.sleep(3.2)
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), DelayedReadyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        probe = launcher._http_probe(
            f"http://127.0.0.1:{server.server_port}/health/ready",
            timeout=launcher.READINESS_PROBE_TIMEOUTS["semanticCore"],
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert probe.status_code == 200
    assert probe.elapsed_ms >= 3_000


def test_semantic_core_probe_fails_once_at_its_bounded_deadline() -> None:
    attempts: list[None] = []

    class DelayedReadyHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            attempts.append(None)
            time.sleep(5.0)
            try:
                self.send_response(200)
                self.end_headers()
            except OSError:
                pass

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), DelayedReadyHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        probe = launcher._http_probe(
            f"http://127.0.0.1:{server.server_port}/health/ready",
            timeout=launcher.READINESS_PROBE_TIMEOUTS["semanticCore"],
        )
    finally:
        elapsed = time.monotonic() - started
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert probe.status_code is None
    assert probe.failure == "timeout"
    assert 3.5 <= elapsed < 5.0
    assert len(attempts) == 1


def test_readiness_failure_log_keeps_only_safe_health_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "launcher.log"
    probe = launcher.HttpProbeResult(
        503,
        json.dumps(
            {
                "status": "not-ready",
                "semanticCore": "ready",
                "reasonCode": "SEMANTIC_CORE_UNAVAILABLE",
                "detail": "source content and secret",
            }
        ),
        None,
        2_100,
    )

    launcher._append_readiness_failure(log_path, "api", 4.0, probe)

    log = log_path.read_text(encoding="utf-8")
    assert "event=readiness-probe-failed service=api timeoutMs=4000 elapsedMs=2100 httpStatus=503" in log
    assert 'response={"reasonCode":"SEMANTIC_CORE_UNAVAILABLE","semanticCore":"ready","status":"not-ready"}' in log
    assert "source content" not in log
    assert "secret" not in log




def test_process_host_sends_private_graceful_stop(tmp_path: Path) -> None:
    host = launcher.ProcessHost()
    child = host.start(
        "test-service",
        [sys.executable, "-u", "-c", "import sys\nfor line in sys.stdin:\n if line.strip() == 'stop': break"],
        os.environ,
        tmp_path,
    )

    host.check_alive("test-service")
    host.stop("test-service", timeout=5)

    assert child.process.returncode == 0
    assert not host.alive_names()


def test_process_host_assigns_owned_child_to_kill_on_close_job(tmp_path: Path) -> None:
    """Crash-safety consumer behavior: the manager owns the child in a Job Object.

    On Windows the Job Object carries KILL_ON_JOB_CLOSE, so a manager crash takes
    its PostgreSQL/Core/Fuseki/API children down instead of orphaning them with
    locked files and ports. Only the manager's own children are assigned; the
    test never touches foreign processes.
    """
    host = launcher.ProcessHost()
    child = host.start(
        "owned-service",
        [sys.executable, "-u", "-c", "import sys, time\nfor line in sys.stdin:\n time.sleep(60)"],
        os.environ,
        tmp_path,
    )
    try:
        if os.name == "nt":
            assert host.job_handle is not None
            assert host.job_owned("owned-service") is True
        host.check_alive("owned-service")
    finally:
        child.process.kill()
        child.process.wait(timeout=10)
        host.processes.pop("owned-service", None)
        host.close_job()
    assert not host.alive_names()


def test_first_run_provisioning_writes_valid_workspace_once(tmp_path: Path) -> None:
    """Approved first-run contract: selected display name, generated ID, fixed actor."""
    target = tmp_path / "local-runtime.json"
    config = launcher.provision_first_run_workspace(target, display_name="My Projecta Workspace")

    assert launcher.PROJECT_ID_PATTERN.fullmatch(config.project_id)
    assert config.project_name == "My Projecta Workspace"
    assert config.actor_id == launcher.FIRST_RUN_ACTOR_ID
    reread = launcher.read_workspace_config(target)
    assert reread == config
    with pytest.raises(launcher.RuntimeFailure):
        launcher.provision_first_run_workspace(target, display_name="My Projecta Workspace")


def test_first_run_provisioning_never_overwrites_existing_config(tmp_path: Path) -> None:
    target = tmp_path / "local-runtime.json"
    target.write_text('{"formatVersion": 1}', encoding="utf-8")
    with pytest.raises(launcher.RuntimeFailure) as failure:
        launcher.provision_first_run_workspace(target)

    assert failure.value.code == "LOCAL_PROJECT_CONFIGURATION_INVALID"


def test_backup_restore_preserves_pre_restore_state(local_paths: launcher.ProjectaPaths) -> None:
    manager = launcher.BackupManager(local_paths)
    backup_id = manager.create()
    (local_paths.data / "postgres" / "database.bin").write_bytes(b"changed database")
    (local_paths.data / "fuseki" / "store.bin").write_bytes(b"changed graph store")

    previous_state = manager.restore(backup_id)

    assert (local_paths.data / "postgres" / "database.bin").read_bytes() == b"original database"
    assert (local_paths.data / "fuseki" / "store.bin").read_bytes() == b"original graph store"
    assert (previous_state / "data" / "postgres" / "database.bin").read_bytes() == b"changed database"
    assert (previous_state / "data" / "fuseki" / "store.bin").read_bytes() == b"changed graph store"


def test_restore_failure_rolls_back_and_retains_attempted_state(
    local_paths: launcher.ProjectaPaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = launcher.BackupManager(local_paths)
    backup_id = manager.create()
    (local_paths.data / "postgres" / "database.bin").write_bytes(b"changed database")
    original_move = launcher._move_state
    calls = 0

    def fail_during_placement(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        # Phase one moves every live entry aside (4 snapshot roots); fail on the
        # first phase-two placement so rollback must restore all four originals.
        if calls == 5:
            raise OSError("synthetic restore failure during staged placement")
        original_move(source, destination)

    monkeypatch.setattr(launcher, "_move_state", fail_during_placement)
    with pytest.raises(launcher.RuntimeFailure) as failure:
        manager.restore(backup_id)

    assert failure.value.code == "BACKUP_RESTORE_ROLLED_BACK"
    assert (local_paths.data / "postgres" / "database.bin").read_bytes() == b"changed database"
    failed_state = next(local_paths.recovery.glob(f"failed-restore-{backup_id}-*"))
    assert (failed_state / "data" / "postgres" / "database.bin").read_bytes() == b"original database"


def test_restore_replaces_existing_directories_without_winerror5(
    local_paths: launcher.ProjectaPaths,
) -> None:
    """Windows boundary: restoring over existing non-empty directories must not raise WinError 5."""
    manager = launcher.BackupManager(local_paths)
    backup_id = manager.create()
    (local_paths.data / "postgres" / "database.bin").write_bytes(b"changed database")
    (local_paths.data / "fuseki" / "extra-live-file.bin").write_bytes(b"live-only file")

    previous_state = manager.restore(backup_id)

    assert (local_paths.data / "postgres" / "database.bin").read_bytes() == b"original database"
    assert not (local_paths.data / "fuseki" / "extra-live-file.bin").exists()
    assert (previous_state / "data" / "postgres" / "database.bin").read_bytes() == b"changed database"


def test_restore_partial_failure_preserves_full_original_state(
    local_paths: launcher.ProjectaPaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Partial restore failure must leave every original store intact, not a mixed state."""
    manager = launcher.BackupManager(local_paths)
    backup_id = manager.create()
    (local_paths.data / "fuseki" / "store.bin").write_bytes(b"changed graph store")
    original_move = launcher._move_state
    state = {"failed": False}

    def fail_once_on_secrets_placement(source: Path, destination: Path) -> None:
        # A transient placement failure: rollback moves must then proceed normally.
        if destination == local_paths.data_root / "secrets" / "launcher.dpapi" and not state["failed"]:
            state["failed"] = True
            raise OSError("synthetic late restore failure")
        original_move(source, destination)

    monkeypatch.setattr(launcher, "_move_state", fail_once_on_secrets_placement)
    with pytest.raises(launcher.RuntimeFailure) as failure:
        manager.restore(backup_id)

    assert failure.value.code == "BACKUP_RESTORE_ROLLED_BACK"
    assert (local_paths.data / "postgres" / "database.bin").read_bytes() == b"original database"
    assert (local_paths.data / "fuseki" / "store.bin").read_bytes() == b"changed graph store"
    assert (local_paths.data / "sqlite" / "catalog.db").read_bytes() == b"original catalog"
    assert (local_paths.data / "evidence" / "record.json").read_text(encoding="utf-8") == "original evidence"


def test_backup_restore_rejects_unmanifested_files(local_paths: launcher.ProjectaPaths) -> None:
    manager = launcher.BackupManager(local_paths)
    backup_id = manager.create()
    (local_paths.backups / backup_id / "items" / "data" / "unverified.bin").write_bytes(b"injected")

    with pytest.raises(launcher.RuntimeFailure, match="incomplete or changed") as failure:
        manager.restore(backup_id)

    assert failure.value.code == "BACKUP_CONTENT_INVALID"
    assert (local_paths.data / "postgres" / "database.bin").read_bytes() == b"original database"


def test_backup_requires_runtime_ports_to_be_quiescent(
    local_paths: launcher.ProjectaPaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        monkeypatch.setattr(launcher, "PORTS", {"occupied": listener.getsockname()[1]})

        with pytest.raises(launcher.RuntimeFailure) as failure:
            launcher.BackupManager(local_paths).create()

    assert failure.value.code == "RUNTIME_MUST_BE_STOPPED"


def test_unsigned_update_package_is_refused(local_paths: launcher.ProjectaPaths) -> None:
    package = local_paths.package_root / "update-candidate"
    package.mkdir(parents=True)
    (package / "runtime-manifest.json").write_text(
        json.dumps(
            {
                "formatVersion": 1,
                "projectaVersion": "0.7.0",
                "dataContractVersion": 1,
                "releaseEligible": True,
                "distributionChannel": "signed-release",
                "signatureAlgorithm": "Ed25519",
                "runtimeVersions": dict(launcher.RUNTIME_VERSIONS),
                "noticeFiles": ["THIRD-PARTY-NOTICES.md"],
                "files": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(launcher.RuntimeFailure) as failure:
        launcher.apply_update(local_paths, package)

    assert failure.value.code == "UPDATE_SIGNATURE_REQUIRED"

def test_staged_runtime_override_never_authorizes_host_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROJECTA_LAUNCHER_PACKAGE_ROOT", "staged-package")
    monkeypatch.setenv("PROJECTA_LAUNCHER_DATA_ROOT", "staged-data")
    manifest = {
        "projectaVersion": "0.7.0",
        "releaseEligible": False,
        "distributionChannel": "host-validation",
    }

    for public_key in (None, "owner-key"):
        monkeypatch.setattr(launcher, "RELEASE_UPDATE_PUBLIC_KEY_B64", public_key)
        with pytest.raises(launcher.RuntimeFailure) as failure:
            launcher._require_package_distribution(manifest)
        assert failure.value.code == "PACKAGE_SIGNATURE_REQUIRED"


def test_only_exact_0_7_0_unsigned_prerelease_exception_is_enabled() -> None:
    authorized = {
        "projectaVersion": "0.7.0",
        "releaseEligible": False,
        "distributionChannel": launcher.UNSIGNED_PRE_RELEASE_CHANNEL,
        "unsignedPreReleaseException": launcher.UNSIGNED_PRE_RELEASE_EXCEPTION,
    }

    launcher._require_package_distribution(authorized)

    unauthorized = (
        {
            **authorized,
            "projectaVersion": "0.7.1",
            "unsignedPreReleaseException": "projecta-0.7.1-unsigned-pre-release-test",
        },
        {**authorized, "unsignedPreReleaseException": "another-exception"},
        {**authorized, "distributionChannel": "host-validation"},
    )
    for manifest in unauthorized:
        with pytest.raises(launcher.RuntimeFailure) as failure:
            launcher._require_package_distribution(manifest)
        assert failure.value.code == "PACKAGE_SIGNATURE_REQUIRED"


def test_signed_update_manifest_verifies_with_explicit_owner_key(tmp_path: Path) -> None:
    package = tmp_path / "update"
    package.mkdir()
    public_key, _, _ = _signed_update_package(package)

    manifest = launcher._verify_update_package(package, trusted_public_key=public_key)

    assert manifest["projectaVersion"] == "0.7.0"
    assert manifest["releaseEligible"] is True


def test_signed_update_rejects_wrong_key_and_tampered_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    package = tmp_path / "update"
    package.mkdir()
    public_key, _, payload = _signed_update_package(package)
    monkeypatch.setattr(launcher, "RELEASE_UPDATE_PUBLIC_KEY_B64", None)
    with pytest.raises(launcher.RuntimeFailure) as missing_anchor:
        launcher._verify_update_package(package)
    assert missing_anchor.value.code == "UPDATE_TRUST_ANCHOR_MISSING"
    wrong_key = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    with pytest.raises(launcher.RuntimeFailure) as wrong_signature:
        launcher._verify_update_package(package, trusted_public_key=wrong_key)
    assert wrong_signature.value.code == "UPDATE_SIGNATURE_INVALID"

    assert len(public_key) == 32
    payload.write_bytes(b"tampered executable")
    with pytest.raises(launcher.RuntimeFailure) as bad_contents:
        launcher._verify_update_package(package, trusted_public_key=public_key)
    assert bad_contents.value.code == "UPDATE_PACKAGE_CONTENT_INVALID"


@pytest.mark.parametrize(
    "filename",
    [
        "vcruntime140.dll",
        "msvcr120.dll",
        "VC_redist.x64.exe",
        "vcredist_x64.exe",
    ],
)
def test_package_inventory_rejects_visual_cpp_runtime_payload(filename: str, tmp_path: Path) -> None:
    package = tmp_path / "package"
    runtime = package / "runtime"
    runtime.mkdir(parents=True)
    payload = runtime / filename
    payload.write_bytes(b"prohibited Microsoft Visual C++ payload")
    manifest = {
        "files": [
            {
                "path": f"runtime/{filename}",
                "size": payload.stat().st_size,
                "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
            }
        ]
    }

    with pytest.raises(launcher.RuntimeFailure) as failure:
        launcher._verify_package_inventory(package, manifest, error_code="PACKAGE_CONTENT_INVALID")

    assert failure.value.code == "PACKAGE_CONTENT_INVALID"

def _workspace_registry(
    tmp_path: Path,
    header: tuple[str, str],
    projects: list[tuple[str, str]],
) -> Path:
    target = tmp_path / "local-runtime.json"
    target.write_text(
        json.dumps(
            {
                "formatVersion": 1,
                "projectId": header[0],
                "projectName": header[1],
                "actorId": launcher.FIRST_RUN_ACTOR_ID,
                "projects": [
                    {"projectId": project_id, "projectName": name}
                    for project_id, name in projects
                ],
            }
        ),
        encoding="utf-8",
    )
    return target


def test_allowlist_accepts_repaired_primary_after_fresh_import(tmp_path: Path) -> None:
    """A fresh import after last-project deletion re-points the serving primary.

    The header and first entry agree with each other even though the stale
    first-run identity is gone; the allowlist must serve the repaired set.
    """
    primary = launcher.WorkspaceConfig(
        "my-projecta-workspace", "My Projecta Workspace", launcher.FIRST_RUN_ACTOR_ID
    )
    target = _workspace_registry(
        tmp_path, ("fresh-project", "Fresh Project"), [("fresh-project", "Fresh Project")]
    )
    assert launcher.workspace_project_ids(target, primary) == ["fresh-project"]


def test_allowlist_still_refuses_header_entry_disagreement(tmp_path: Path) -> None:
    """A registry whose header disagrees with its first entry stays invalid."""
    primary = launcher.WorkspaceConfig(
        "my-projecta-workspace", "My Projecta Workspace", launcher.FIRST_RUN_ACTOR_ID
    )
    target = _workspace_registry(
        tmp_path, ("evil-project", "Evil"), [("fresh-project", "Fresh Project")]
    )
    with pytest.raises(launcher.RuntimeFailure) as failure:
        launcher.workspace_project_ids(target, primary)
    assert failure.value.code == "LOCAL_PROJECT_CONFIGURATION_INVALID"


def test_allowlist_keeps_serving_empty_catalog_without_resurrection(tmp_path: Path) -> None:
    """The persisted empty catalog still serves zero projects after the fix."""
    primary = launcher.WorkspaceConfig(
        "my-projecta-workspace", "My Projecta Workspace", launcher.FIRST_RUN_ACTOR_ID
    )
    target = _workspace_registry(
        tmp_path, ("my-projecta-workspace", "My Projecta Workspace"), []
    )
    assert launcher.workspace_project_ids(target, primary) == []

