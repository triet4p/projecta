"""Staged-commit behavior tests for the per-user NSIS installer transaction.

The 0.7.1 unsigned installer stages the full application tree into a sibling
``*.staging`` directory and then renames it over the install directory. The
transaction fails closed when the installer process still has the staging
directory as its working directory: Windows refuses to rename a process's
own current directory, so the commit rename always fails and the installer
reports that the staged files could not be committed. These tests exercise
that exact mechanics through the real pinned NSIS 3.13 toolchain in
throwaway directories: a fresh install must commit the staged payload, an
upgrade must replace the previous tree, and a forced commit failure must
leave the previous installation in place. Nothing here touches the owner
profile, HKCU, shortcuts, or the network.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
NSIS_COMPILER = (
    ROOT / "build" / "tools" / "nsis-3.13" / "distribution" / "nsis-3.13" / "makensis.exe"
)
INSTALLER_SCRIPT = ROOT / "scripts" / "projecta-setup.nsi"

_COPY_COMMIT_SECTION = r"""
Section "probe"
  CreateDirectory "${TARGET_ROOT}"
  GetTempFileName $0 "${TARGET_ROOT}"
  Delete "$0"
  StrCpy $1 "$0.staging"
  GetTempFileName $0 "${TARGET_ROOT}"
  Delete "$0"
  StrCpy $2 "$0.previous"
  CreateDirectory "$1"
  SetOutPath "$1"
  File /r "${SOURCE_DIR}\*"
  StrCpy $3 0
  SetOutPath "${TARGET_ROOT}"
  IfFileExists "${TARGET_INST}" 0 stageReady
  IfFileExists "${TARGET_INST}\*.*" 0 stageReady
  ClearErrors
  Rename "${TARGET_INST}" "$2"
  StrCpy $3 1
stageReady:
  SetOutPath "${TARGET_ROOT}"
  ClearErrors
  IfFileExists "${TARGET_INST}" 0 commitRename
  RMDir "${TARGET_INST}"
  ClearErrors
commitRename:
  Rename "$1" "${TARGET_INST}"
  IfErrors commitFailed 0
  StrCmp $3 1 removePreviousTemp cleanupTemp
cleanupTemp:
  RMDir "$2"
removePreviousTemp:
  RMDir /r "$2"
  Goto finishCommit
finishCommit:
  FileOpen $9 "${TARGET_ROOT}\RESULT.txt" w
  FileWrite $9 "COMMITTED"
  FileClose $9
  Goto done
commitFailed:
  StrCmp $3 1 0 preserved
  ClearErrors
  Rename "$2" "${TARGET_INST}"
preserved:
  RMDir /r "$1"
  RMDir "$2"
  FileOpen $9 "${TARGET_ROOT}\RESULT.txt" w
  FileWrite $9 "NOT_COMMITTED"
  FileClose $9
done:
SectionEnd
"""


_SABOTAGED_COMMIT_SECTION = _COPY_COMMIT_SECTION.replace(
    '  SetOutPath "${TARGET_ROOT}"\n',
    "",
)


def _compile_probe(tmp_path: Path, *, body: str) -> Path:
    source = tmp_path / "payload"
    (source).mkdir()
    (source / "hello.txt").write_text("probe payload\n", encoding="utf-8")
    script = tmp_path / "probe.nsi"
    script.write_text(
        "Unicode true\n"
        'Name "CommitProbe"\n'
        'OutFile "${OUTPUT_FILE}"\n'
        'InstallDir "${TARGET_INST}"\n'
        "RequestExecutionLevel user\n"
        "ShowInstDetails show\n" + body,
        encoding="utf-8",
    )
    output = tmp_path / "probe.exe"
    completed = subprocess.run(
        [
            str(NSIS_COMPILER),
            f"/DSOURCE_DIR={source}",
            f"/DTARGET_ROOT={tmp_path}",
            f"/DTARGET_INST={tmp_path / 'app'}",
            f"/DOUTPUT_FILE={output}",
            str(script),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert output.is_file()
    return output


def _run_silent(installer: Path, timeout: int = 120) -> None:
    completed = subprocess.run(
        [str(installer), "/S"],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]


@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_staged_commit_installs_payload(tmp_path: Path) -> None:
    """A fresh install commits the staged payload to the target directory."""

    installer = _compile_probe(tmp_path, body=_COPY_COMMIT_SECTION)
    _run_silent(installer)

    assert (tmp_path / "RESULT.txt").read_text(encoding="utf-8") == "COMMITTED"
    assert (tmp_path / "app" / "hello.txt").read_text(encoding="utf-8") == "probe payload\n"

@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_staged_commit_installs_into_empty_target_directory(tmp_path: Path) -> None:
    """A pre-created but empty target directory still commits the payload."""

    previous = tmp_path / "app"
    previous.mkdir()

    installer = _compile_probe(tmp_path, body=_COPY_COMMIT_SECTION)
    _run_silent(installer)

    assert (tmp_path / "RESULT.txt").read_text(encoding="utf-8") == "COMMITTED"
    assert (previous / "hello.txt").read_text(encoding="utf-8") == "probe payload\n"



@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_staged_commit_upgrade_replaces_previous_install(tmp_path: Path) -> None:
    """An upgrade moves the previous tree aside and commits the new payload."""

    previous = tmp_path / "app"
    previous.mkdir()
    (previous / "legacy.txt").write_text("previous version\n", encoding="utf-8")

    installer = _compile_probe(tmp_path, body=_COPY_COMMIT_SECTION)
    _run_silent(installer)

    assert (tmp_path / "RESULT.txt").read_text(encoding="utf-8") == "COMMITTED"
    assert (previous / "hello.txt").read_text(encoding="utf-8") == "probe payload\n"
    assert not (previous / "legacy.txt").exists()

@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_forced_commit_failure_preserves_previous_install(tmp_path: Path) -> None:
    """A failed commit restores the previous tree and reports no commit."""

    previous = tmp_path / "app"
    previous.mkdir()
    (previous / "legacy.txt").write_text("previous version\n", encoding="utf-8")

    installer = _compile_probe(tmp_path, body=_SABOTAGED_COMMIT_SECTION)
    _run_silent(installer)

    assert (tmp_path / "RESULT.txt").read_text(encoding="utf-8") == "NOT_COMMITTED"
    assert (previous / "legacy.txt").read_text(encoding="utf-8") == "previous version\n"
    assert not (previous / "hello.txt").exists()


@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_shipped_installer_script_compiles_against_fixture_package(tmp_path: Path) -> None:
    """The shipped installer script still compiles with the pinned toolchain."""

    package = tmp_path / "package"
    package.mkdir()
    (package / "ProjectaStart.ps1").write_text("exit 0\n", encoding="utf-8")
    output = tmp_path / "shipped.exe"
    completed = subprocess.run(
        [
            str(NSIS_COMPILER),
            f"/DPACKAGE_DIR={package}",
            f"/DOUTPUT_FILE={output}",
            str(INSTALLER_SCRIPT),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert output.is_file()


def test_installer_refuses_package_missing_tauri_inputs(tmp_path: Path) -> None:
    """A provenance record without Tauri inputs refuses before any install."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_windows_installer as installer

    with pytest.raises(SystemExit) as failure:
        installer._require_tauri_input_agreement({"sourceFiles": []})
    assert "omits required Tauri inputs" in str(failure.value)


def test_installer_refuses_tampered_tauri_input(tmp_path: Path) -> None:
    """A recorded Tauri input that differs from the release tree refuses."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_windows_installer as installer

    records = [installer._source_file_record(ROOT / path) for path in (
        "apps/desktop/package.json",
        "apps/desktop/package-lock.json",
        "apps/desktop/src-tauri/Cargo.toml",
        "apps/desktop/src-tauri/Cargo.lock",
        "apps/desktop/src-tauri/tauri.conf.json",
    )]
    records[0] = {**records[0], "sha256": "0" * 64}
    with pytest.raises(SystemExit) as failure:
        installer._require_tauri_input_agreement({"sourceFiles": records})
    assert "differs from the release source" in str(failure.value)


def _installer_test_anchor(monkeypatch: pytest.MonkeyPatch):
    """Create a disposable owner anchor and point installer build-time config at it."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sys.path.insert(0, str(ROOT / "scripts"))
    import build_windows_installer as installer

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    public_b64 = base64.b64encode(public_key).decode("ascii")
    monkeypatch.setenv("PROJECTA_UPDATE_PUBLIC_KEY_B64", public_b64)
    return installer, private_key, public_key


def _signed_release_manifest(
    package: Path, fingerprint: str, *, signature: bytes | None = None
) -> dict:
    """Write a signed-release-shaped manifest exercising the real installer gate order."""
    import hashlib
    import json

    sys.path.insert(0, str(ROOT / "scripts"))
    import build_windows_installer as installer
    import projecta_local as launcher

    manifest = {
        "formatVersion": 1,
        "projectaVersion": installer.APP_VERSION,
        "dataContractVersion": 1,
        "releaseEligible": True,
        "distributionChannel": "signed-release",
        "signatureAlgorithm": "Ed25519",
        "publicKeyFingerprint": fingerprint,
        "authenticodeSigning": None,
        "runtimeVersions": dict(launcher.RUNTIME_VERSIONS),
        "vcRuntimePrerequisite": dict(launcher.VC_RUNTIME_PREREQUISITE),
        "webview2RuntimePrerequisite": dict(launcher.WEBVIEW2_RUNTIME_PREREQUISITE),
        "sourceRevision": "rev-test",
        "sourceRevisionMeaning": "test",
        "sourceProvenance": {
            "file": "runtime/source-provenance.json",
            "sha256": "x",
            "sourceRevision": "rev-test",
            "sourceFilesSha256": "y",
        },
        "noticeFiles": [],
        "files": [],
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    (package / "runtime-manifest.json").write_bytes(manifest_bytes)
    if signature is not None:
        import base64

        (package / "runtime-manifest.sig").write_bytes(base64.b64encode(signature) + b"\n")
    return manifest


def test_installer_validate_accepts_signed_release_with_notsigned_authenticode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An Ed25519-signed release package with absent Authenticode passes the package gate."""
    import hashlib

    installer, private_key, public_key = _installer_test_anchor(monkeypatch)
    import projecta_local as launcher

    package = tmp_path / "package"
    package.mkdir()
    fingerprint = hashlib.sha256(public_key).hexdigest()
    manifest_bytes_holder: dict[str, bytes] = {}
    manifest = _signed_release_manifest(package, fingerprint)
    manifest_bytes_holder["bytes"] = (package / "runtime-manifest.json").read_bytes()
    import base64

    (package / "runtime-manifest.sig").write_bytes(
        base64.b64encode(private_key.sign(manifest_bytes_holder["bytes"])) + b"\n"
    )
    provenance = {
        "sourceFiles": [
            {"path": path, "size": 1, "sha256": "0" * 64}
            for path in (
                "apps/desktop/package.json",
                "apps/desktop/package-lock.json",
                "apps/desktop/src-tauri/Cargo.toml",
                "apps/desktop/src-tauri/Cargo.lock",
                "apps/desktop/src-tauri/tauri.conf.json",
            )
        ]
    }
    live_records = {
        path: {"path": path, "size": 1, "sha256": "0" * 64}
        for path in (
            "apps/desktop/package.json",
            "apps/desktop/package-lock.json",
            "apps/desktop/src-tauri/Cargo.toml",
            "apps/desktop/src-tauri/Cargo.lock",
            "apps/desktop/src-tauri/tauri.conf.json",
        )
    }
    monkeypatch.setattr(installer, "_package_source_provenance", lambda package, manifest: provenance)
    monkeypatch.setattr(installer, "_source_file_record", lambda path: live_records[path.relative_to(installer.ROOT).as_posix()])
    monkeypatch.setattr(installer, "validate_desktop_locks", lambda root: {})
    real_anchor = launcher.RELEASE_UPDATE_PUBLIC_KEY_B64
    monkeypatch.setattr(launcher, "load_runtime_manifest", lambda paths: manifest)

    assert installer._validate_package(package) == manifest
    assert launcher.RELEASE_UPDATE_PUBLIC_KEY_B64 == real_anchor


def test_installer_validate_refuses_signed_release_without_signature_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A signed-release claim without the detached Ed25519 signature refuses."""
    import hashlib

    installer, _, public_key = _installer_test_anchor(monkeypatch)

    package = tmp_path / "package"
    package.mkdir()
    _signed_release_manifest(package, hashlib.sha256(public_key).hexdigest())

    with pytest.raises(SystemExit) as failure:
        installer._validate_package(package)

    assert "signed-release contract" in str(failure.value)


def test_installer_validate_refuses_signed_release_with_wrong_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A manifest signed by another key refuses against the configured owner anchor."""
    import base64
    import hashlib

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    installer, _, public_key = _installer_test_anchor(monkeypatch)

    package = tmp_path / "package"
    package.mkdir()
    manifest = _signed_release_manifest(package, hashlib.sha256(public_key).hexdigest())
    del manifest
    other_key = Ed25519PrivateKey.generate()
    other_signature = other_key.sign((package / "runtime-manifest.json").read_bytes())
    (package / "runtime-manifest.sig").write_bytes(base64.b64encode(other_signature) + b"\n")

    with pytest.raises(SystemExit) as failure:
        installer._validate_package(package)

    assert "signature is invalid" in str(failure.value)


def test_installer_validate_refuses_signed_release_with_tampered_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A signed manifest modified after signing refuses against the owner anchor."""
    import base64
    import hashlib

    installer, private_key, public_key = _installer_test_anchor(monkeypatch)

    package = tmp_path / "package"
    package.mkdir()
    _signed_release_manifest(package, hashlib.sha256(public_key).hexdigest())
    manifest_bytes = (package / "runtime-manifest.json").read_bytes()
    (package / "runtime-manifest.sig").write_bytes(
        base64.b64encode(private_key.sign(manifest_bytes)) + b"\n"
    )
    import json

    manifest = json.loads((package / "runtime-manifest.json").read_bytes())
    manifest["noticeFiles"] = ["THIRD-PARTY-NOTICES.md"]
    (package / "runtime-manifest.json").write_bytes(
        (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    )

    with pytest.raises(SystemExit) as failure:
        installer._validate_package(package)

    assert "signature is invalid" in str(failure.value)


def test_installer_validate_refuses_signed_release_without_configured_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A signed-release package without build-time owner configuration refuses closed."""
    import hashlib

    sys.path.insert(0, str(ROOT / "scripts"))
    import build_windows_installer as installer
    import projecta_local as launcher

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    monkeypatch.delenv("PROJECTA_UPDATE_PUBLIC_KEY_B64", raising=False)

    package = tmp_path / "package"
    package.mkdir()
    _signed_release_manifest(
        package,
        hashlib.sha256(public_key).hexdigest(),
        signature=private_key.sign(b"placeholder"),
    )

    with pytest.raises(SystemExit) as failure:
        installer._validate_package(package)

    assert "trust anchor is not configured" in str(failure.value)
    assert launcher.RELEASE_UPDATE_PUBLIC_KEY_B64 is None
