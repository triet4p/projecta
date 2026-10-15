"""Build the per-user Projecta Windows setup file from an authorized package.

The buildable shape is an owner Ed25519-signed release package
(``releaseEligible=true``, ``distributionChannel=signed-release``) whose Windows
binaries are truthfully NotSigned when Authenticode is unconfigured. The
historical 0.7.x unsigned test exception is recognized only to be refused: it is
authorized for the release it names, which the current version pins are not.
Anything else refuses.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import subprocess
import struct
import sys
import uuid
from pathlib import Path
from typing import Any
import re

import projecta_local as launcher
from check_release_contract import ReleaseContractError, validate_desktop_locks

ROOT = Path(__file__).resolve().parents[1]
APP_VERSION = "1.0.0"
CHANNEL = "unsigned-pre-release-test"
EXCEPTION = "projecta-0.7.1-unsigned-pre-release-test"
NSIS_VERSION = "3.13"
NSIS_ARCHIVE_SHA256 = "ba63dffc4410ee89193e1cb5a41989991bd77c61068da17e3156d136b7b0b3d8"
NSIS_ARCHIVE_URL = "https://sourceforge.net/projects/nsis/files/NSIS%203/3.13/nsis-3.13.zip/"
INSTALLER_NAME = "Projecta-Setup-1.0.0.exe"
DEFAULT_NSIS_ROOT = ROOT / "build" / "tools" / "nsis-3.13" / "distribution" / "nsis-3.13"
DEFAULT_NSIS_ARCHIVE = ROOT / "build" / "tools" / "nsis-3.13" / "nsis-3.13.zip"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rooted(path: Path) -> Path:
    expanded = path.expanduser()
    return Path(os.path.abspath(expanded if expanded.is_absolute() else ROOT / expanded))

def _source_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    revision = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise SystemExit("the installer source commit could not be recorded.")
    return revision

def _records_sha256(records: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: str(item["path"]).casefold()):
        digest.update(
            f"{record['path']}\t{record['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _source_file_record(path: Path) -> dict[str, object]:
    if path.is_symlink():
        raise SystemExit(f"installer build source input is unsafe: {path}")
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError as error:
        raise SystemExit("installer build source inputs must be inside the project repository.") from error
    if not resolved.is_file():
        raise SystemExit(f"installer build source input is missing: {relative}")
    return {
        "path": relative,
        "size": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _package_source_provenance(package: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    reference = manifest.get("sourceProvenance")
    if (
        not isinstance(reference, dict)
        or reference.get("file") != "runtime/source-provenance.json"
        or reference.get("sourceRevision") != manifest.get("sourceRevision")
    ):
        raise SystemExit("the package does not contain a supported build-source provenance reference.")
    provenance_path = package / str(reference["file"])
    if not provenance_path.is_file() or provenance_path.is_symlink():
        raise SystemExit("the package build-source provenance file is missing or unsafe.")
    if _sha256(provenance_path) != reference.get("sha256"):
        raise SystemExit("the package build-source provenance file does not match its manifest digest.")
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit("the package build-source provenance file is invalid.") from error
    records = provenance.get("sourceFiles")
    if (
        not isinstance(records, list)
        or provenance.get("sourceRevision") != manifest.get("sourceRevision")
        or provenance.get("sourceFilesSha256") != reference.get("sourceFilesSha256")
        or _records_sha256(records) != reference.get("sourceFilesSha256")
    ):
        raise SystemExit("the package build-source provenance digest is inconsistent.")
    return provenance


def _require_tauri_input_agreement(provenance: dict[str, Any]) -> None:
    """Refuse a package whose recorded Tauri inputs disagree with the release tree.

    The installer never rebuilds the Tauri host; it binds the staged package to
    the same version/lock agreement the release contract enforces, so a
    tampered or mismatched Tauri input refuses here instead of shipping.
    """
    records = provenance.get("sourceFiles")
    if not isinstance(records, list):
        raise SystemExit("the package build-source provenance digest is inconsistent.")
    by_path = {
        record["path"]: record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }
    required = (
        "apps/desktop/package.json",
        "apps/desktop/package-lock.json",
        "apps/desktop/src-tauri/Cargo.toml",
        "apps/desktop/src-tauri/Cargo.lock",
        "apps/desktop/src-tauri/tauri.conf.json",
    )
    missing = [path for path in required if path not in by_path]
    if missing:
        raise SystemExit(f"the package provenance omits required Tauri inputs: {missing}")
    live: dict[str, dict[str, object]] = {}
    for path in required:
        live[path] = _source_file_record(ROOT / path)
        if by_path[path] != live[path]:
            raise SystemExit(f"the packaged Tauri input differs from the release source: {path}")
    try:
        validate_desktop_locks(ROOT)
    except ReleaseContractError as error:
        raise SystemExit(f"the Tauri desktop inputs do not satisfy the release contract: {error}") from error

def _installer_release_trust_anchor() -> bytes:
    """Return the owner Ed25519 trust anchor for build-time installer validation.

    The anchor comes only from the authorized build-time owner configuration
    (``PROJECTA_UPDATE_PUBLIC_KEY_B64``). The package's self-declared
    fingerprint is never trusted: the manifest signature must verify against
    this configured anchor. Unsigned-only 0.7.1 exception packages never reach
    this helper.
    """
    encoded = os.environ.get("PROJECTA_UPDATE_PUBLIC_KEY_B64")
    if not encoded:
        raise SystemExit(
            "the owner Ed25519 trust anchor is not configured; "
            "PROJECTA_UPDATE_PUBLIC_KEY_B64 is required to validate a signed-release package."
        )
    try:
        public_key = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise SystemExit("PROJECTA_UPDATE_PUBLIC_KEY_B64 is invalid.") from error
    if len(public_key) != 32:
        raise SystemExit("PROJECTA_UPDATE_PUBLIC_KEY_B64 must encode a 32-byte Ed25519 public key.")
    return public_key

def _authenticode_status(path: Path) -> str:
    with path.open("rb") as stream:
        dos_header = stream.read(64)
        if len(dos_header) != 64 or dos_header[:2] != b"MZ":
            raise SystemExit("the generated setup file is not a valid Windows PE executable.")
        pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
        stream.seek(pe_offset)
        if stream.read(4) != b"PE\0\0":
            raise SystemExit("the generated setup file has no valid PE header.")
        file_header = stream.read(20)
        if len(file_header) != 20:
            raise SystemExit("the generated setup file has a truncated PE file header.")
        optional_size = struct.unpack_from("<H", file_header, 16)[0]
        optional_header = stream.read(optional_size)
    if len(optional_header) != optional_size or len(optional_header) < 2:
        raise SystemExit("the generated setup file has a truncated PE optional header.")
    magic = struct.unpack_from("<H", optional_header)[0]
    if magic == 0x10B:
        number_offset, directories_offset = 92, 96
    elif magic == 0x20B:
        number_offset, directories_offset = 108, 112
    else:
        raise SystemExit("the generated setup file has an unsupported PE optional header.")
    if len(optional_header) < number_offset + 4:
        raise SystemExit("the generated setup file omits its PE data-directory count.")
    directory_count = struct.unpack_from("<I", optional_header, number_offset)[0]
    if directory_count <= 4:
        return "NotSigned"
    certificate_entry = directories_offset + 4 * 8
    if len(optional_header) < certificate_entry + 8:
        raise SystemExit("the generated setup file has a truncated PE security directory.")
    certificate_offset, certificate_size = struct.unpack_from("<II", optional_header, certificate_entry)
    if certificate_offset == 0 and certificate_size == 0:
        return "NotSigned"
    if certificate_offset == 0 or certificate_size == 0 or certificate_offset + certificate_size > path.stat().st_size:
        raise SystemExit("the generated setup file contains an invalid Authenticode certificate table.")
    return "Signed"

def _validate_package(package: Path) -> dict[str, Any]:
    if package.is_symlink() or not package.is_dir():
        raise SystemExit("the package directory must be a real directory.")
    if APP_VERSION != launcher.APP_VERSION:
        raise SystemExit("the installer and launcher version pins do not match.")
    manifest_path = package / "runtime-manifest.json"
    signature_path = package / "runtime-manifest.sig"
    try:
        manifest = json.loads(manifest_path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit("the package manifest is missing or invalid.") from error
    if not isinstance(manifest, dict):
        raise SystemExit("the package manifest is missing or invalid.")
    if manifest.get("projectaVersion") != APP_VERSION:
        raise SystemExit("the package version does not match the installer version pin.")
    if manifest.get("releaseEligible") is True:
        # Build-time installer validation uses only the authorized owner
        # configuration as its trust anchor. The worktree launcher carries no
        # frozen anchor, and the package's self-declared fingerprint is never
        # trusted: the detached manifest signature must verify against the
        # configured anchor before any other release check runs.
        anchor = _installer_release_trust_anchor()
        if (
            manifest.get("distributionChannel") != "signed-release"
            or "unsignedPreReleaseException" in manifest
            or manifest.get("signatureAlgorithm") != "Ed25519"
            or not signature_path.is_file()
            or signature_path.is_symlink()
        ):
            raise SystemExit("the owner release package does not satisfy the signed-release contract.")
        try:
            manifest_bytes = manifest_path.read_bytes()
            launcher._verify_ed25519_signature(manifest_bytes, signature_path, anchor)
        except launcher.RuntimeFailure as error:
            raise SystemExit(f"the owner release package signature is invalid: {error.code}") from error
        except OSError as error:
            raise SystemExit("the owner release package manifest could not be read.") from error
        if manifest.get("publicKeyFingerprint") != hashlib.sha256(anchor).hexdigest():
            raise SystemExit("the owner release package fingerprint does not match its trust anchor.")
    elif not (
        manifest.get("releaseEligible") is False
        and manifest.get("distributionChannel") == CHANNEL
        and manifest.get("unsignedPreReleaseException") == EXCEPTION
        and manifest.get("authenticodeSigning") is None
        and not signature_path.exists()
    ):
        raise SystemExit("the package does not match the exact owner-authorized unsigned 0.7.1 exception.")
    paths = launcher.ProjectaPaths(package, ROOT / "build" / "installer-smoke-data-unused")
    previous_anchor = launcher.RELEASE_UPDATE_PUBLIC_KEY_B64
    if manifest.get("releaseEligible") is True:
        launcher.RELEASE_UPDATE_PUBLIC_KEY_B64 = os.environ.get("PROJECTA_UPDATE_PUBLIC_KEY_B64")
    try:
        manifest = launcher.load_runtime_manifest(paths)
        launcher._require_package_distribution(manifest)
    except launcher.RuntimeFailure as error:
        raise SystemExit(f"the package does not satisfy the runtime distribution contract: {error.code}") from error
    finally:
        launcher.RELEASE_UPDATE_PUBLIC_KEY_B64 = previous_anchor
    package_provenance = _package_source_provenance(package, manifest)
    _require_tauri_input_agreement(package_provenance)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build one per-user Projecta Windows installer.")
    parser.add_argument("--package", type=Path, required=True, help="assembled package directory")
    parser.add_argument("--compiler", type=Path, default=DEFAULT_NSIS_ROOT / "makensis.exe")
    parser.add_argument("--nsis-archive", type=Path, default=DEFAULT_NSIS_ARCHIVE)
    parser.add_argument("--script", type=Path, default=ROOT / "scripts" / "projecta-setup.nsi")
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "releases" / INSTALLER_NAME)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)

    if sys.platform != "win32" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        raise SystemExit("the x64 Windows installer must be compiled on a Windows x64 host.")
    package = _rooted(args.package)
    compiler = _rooted(args.compiler)
    nsis_archive = _rooted(args.nsis_archive)
    script = _rooted(args.script)
    output = _rooted(args.output)
    receipt_path = _rooted(args.receipt) if args.receipt is not None else output.with_suffix(output.suffix + ".build.json")
    if output == receipt_path or output.is_relative_to(package) or receipt_path.is_relative_to(package):
        raise SystemExit("installer and receipt outputs must be distinct from each other and outside the package.")
    if output.is_symlink() or output.exists() or receipt_path.is_symlink() or receipt_path.exists():
        raise SystemExit("the installer or receipt output already exists; existing files were left untouched.")
    if not compiler.is_file() or compiler.is_symlink():
        raise SystemExit("the pinned NSIS 3.13 compiler is missing or unsafe.")
    if not nsis_archive.is_file() or nsis_archive.is_symlink():
        raise SystemExit("the pinned NSIS source archive is missing or unsafe.")
    archive_hash = _sha256(nsis_archive)
    if archive_hash != NSIS_ARCHIVE_SHA256:
        raise SystemExit("the NSIS source archive does not match the pinned SHA-256.")
    license_notice = compiler.parent / "COPYING"
    if not license_notice.is_file() or license_notice.is_symlink():
        raise SystemExit("the upstream NSIS COPYING file is missing from the pinned toolchain.")
    compiler_version = subprocess.run(
        [str(compiler), "/VERSION"], capture_output=True, text=True, cwd=ROOT, check=False
    )
    if compiler_version.returncode != 0 or compiler_version.stdout.strip() != f"v{NSIS_VERSION}":
        raise SystemExit(f"NSIS {NSIS_VERSION} is required; found {compiler_version.stdout.strip()}.")
    manifest = _validate_package(package)
    if not script.is_file() or script.is_symlink():
        raise SystemExit("the per-user NSIS installer script is missing or unsafe.")
    source_revision = _source_revision()
    if manifest.get("sourceRevision") != source_revision:
        raise SystemExit("installer and package source base revisions differ.")
    package_provenance = _package_source_provenance(package, manifest)
    installer_source_files = sorted(
        [
            _source_file_record(ROOT / "scripts" / "build_windows_installer.py"),
            _source_file_record(script),
            _source_file_record(Path(launcher.__file__)),
        ],
        key=lambda entry: str(entry["path"]).casefold(),
    )
    package_source_files = {
        record["path"]: record
        for record in package_provenance["sourceFiles"]
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }
    if any(package_source_files.get(entry["path"]) != entry for entry in installer_source_files):
        raise SystemExit("installer source files differ from the package's recorded build inputs.")
    installer_source_provenance = {
        "sourceRevision": source_revision,
        "sourceRevisionMeaning": (
            "Git HEAD at installer build time; sourceFiles records the actual installer inputs."
        ),
        "sourceFiles": installer_source_files,
        "sourceFilesSha256": _records_sha256(installer_source_files),
        "packageSourceProvenanceSha256": manifest["sourceProvenance"]["sha256"],
        "externalInputs": {
            "nsisDistribution": {
                "version": NSIS_VERSION,
                "downloadUrl": NSIS_ARCHIVE_URL,
                "sourceArchiveSha256": archive_hash,
                "sourceArchiveSize": nsis_archive.stat().st_size,
            },
            "compilerExecutableSha256": _sha256(compiler),
            "licenseNoticeSha256": _sha256(license_notice),
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(f".{output.stem}.building-{uuid.uuid4().hex}.exe")
    command = [
        str(compiler),
        f"/DPACKAGE_DIR={package}",
        f"/DOUTPUT_FILE={temporary_output}",
        str(script),
    ]
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, check=False)
    if result.returncode != 0 or not temporary_output.is_file():
        temporary_output.unlink(missing_ok=True)
        details = result.stderr[-4000:] or result.stdout[-4000:]
        raise SystemExit(f"NSIS setup compilation failed: {details}")
    current_source_files = sorted(
        [
            _source_file_record(ROOT / "scripts" / "build_windows_installer.py"),
            _source_file_record(script),
            _source_file_record(Path(launcher.__file__)),
        ],
        key=lambda entry: str(entry["path"]).casefold(),
    )
    if current_source_files != installer_source_files:
        temporary_output.unlink(missing_ok=True)
        raise SystemExit("installer source files changed while NSIS was compiling the candidate.")
    signature_status = _authenticode_status(temporary_output)
    package_authenticode = manifest.get("authenticodeSigning")
    if manifest.get("releaseEligible") is True:
        if package_authenticode is None and signature_status != "NotSigned":
            temporary_output.unlink(missing_ok=True)
            raise SystemExit(f"the unsigned release installer must remain unsigned; Authenticode status was {signature_status}.")
    elif signature_status != "NotSigned":
        temporary_output.unlink(missing_ok=True)
        raise SystemExit(f"the test installer must remain unsigned; Authenticode status was {signature_status}.")
    os.replace(temporary_output, output)
    installer = {
        "file": output.name,
        "size": output.stat().st_size,
        "sha256": _sha256(output),
        "authenticodeStatus": signature_status,
        "windowsPublisherWarning": (
            "Windows cannot verify the publisher; SmartScreen or antivirus software may warn."
            if signature_status == "NotSigned"
            else None
        ),
        "installScope": "Projecta is per-user and not elevated; installing Microsoft's WebView2 or Visual C++ prerequisite may request UAC after user consent.",
        "installDirectory": "%LOCALAPPDATA%\\Programs\\Projecta\\1.0.0",
        "mutableDataDirectory": "%LOCALAPPDATA%\\Projecta",
        "uninstallRetainsMutableData": True,
    }
    receipt = {
        "projectaVersion": APP_VERSION,
        "releaseEligible": manifest.get("releaseEligible"),
        "distributionChannel": manifest.get("distributionChannel"),
        "unsignedPreReleaseException": manifest.get("unsignedPreReleaseException"),
        "installerScriptSha256": _sha256(script),
        "sourceRevision": manifest["sourceRevision"],
        "sourceRevisionMeaning": manifest.get("sourceRevisionMeaning"),
        "sourceProvenance": manifest["sourceProvenance"],
        "installerSourceProvenance": installer_source_provenance,
        "runtimeManifestSha256": _sha256(package / "runtime-manifest.json"),
        "installer": installer,
        "toolchain": {
            "name": "Nullsoft Scriptable Install System",
            "version": NSIS_VERSION,
            "downloadUrl": NSIS_ARCHIVE_URL,
            "sourceArchiveSha256": archive_hash,
            "publisherChecksumListed": False,
            "compilerVersionOutput": compiler_version.stdout.strip(),
            "licenseNoticeBundled": "runtime/installer-tool/NSIS-COPYING.txt",
        },
        "package": str(package),
        "signing": {
            "authenticode": signature_status,
            "packageAuthenticode": package_authenticode,
            "ed25519ReleaseManifest": bool(manifest.get("releaseEligible") is True and (package / "runtime-manifest.sig").is_file()),
            "authenticodeVerification": (
                "no PE IMAGE_DIRECTORY_ENTRY_SECURITY certificate table"
                if signature_status == "NotSigned"
                else "PE IMAGE_DIRECTORY_ENTRY_SECURITY certificate table present; Windows publisher verification applies"
            ),
            "cleanWindowsProof": False,
        },
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"installer {output} sha256={installer['sha256']} size={installer['size']}")
    print(f"authenticode={signature_status}; releaseEligible={manifest.get('releaseEligible')}; channel={manifest.get('distributionChannel')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
