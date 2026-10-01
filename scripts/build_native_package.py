#!/usr/bin/env python3
"""Assemble the Windows per-user native package from genuine staged inputs.

Reads only:
- build/native-dl/*.zip (official CPython embeddable, Temurin JRE, EDB PostgreSQL)
- services/semantic-core/target/{classes,lib} (Maven-built, online-resolved)
- apps/api source + locked dependencies (uv export)
- apps/web/dist (compiled SPA), ontology/, scripts/bootstrap_fuseki.py
- infra/docker/fuseki/config/fuseki-config.ttl (adapted to a template)

Writes build/native-package by default; --output and --archive select new paths.

Fail-closed: refuses to stage when any pinned input, hash, or required file
is missing. Never invents binaries, licenses, or signatures.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import zipfile
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DL = ROOT / "build" / "native-dl"
OUT = ROOT / "build" / "native-package"

APP_VERSION = "0.7.0"
DATA_CONTRACT_VERSION = 1
UNSIGNED_PRE_RELEASE_VERSION = "0.7.0"
UNSIGNED_PRE_RELEASE_CHANNEL = "unsigned-pre-release-test"
UNSIGNED_PRE_RELEASE_EXCEPTION = "projecta-0.7.0-unsigned-pre-release-test"
NSIS_VERSION = "3.13"
NSIS_ARCHIVE_SHA256 = "ba63dffc4410ee89193e1cb5a41989991bd77c61068da17e3156d136b7b0b3d8"
NSIS_DOWNLOAD_URL = "https://sourceforge.net/projects/nsis/files/NSIS%203/3.13/nsis-3.13.zip/"
PYINSTALLER_VERSION = "6.22.3"
ARCHIVE = ROOT / "build" / f"ProjectaLocal-{APP_VERSION}-win-x64-UNSIGNED-PRE-RELEASE-TEST.zip"
RUNTIME_VERSIONS = {
    "python": "3.12.10",
    "java": "21.0.12.1+1",
    "fuseki": "6.2.0",
    "postgresql": "16.15",
}
EXPECTED = {
    "python-embed.zip": {"md5": "fe8ef205f2e9c3ba44d0cf9954e1abd3", "size": 11133606},
    "jre.zip": {"sha256": "d35f31e712f0fcf6ac5a093edc90204fbff22f720ba3950bd09d331d5e621636", "size": 48999141},
    "pg-binaries.zip": {"sha256": None, "size": 371449528},  # EDB publishes no SHA-256; record computed hash
}

PYTHON_SOURCE = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
JRE_SOURCE = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jre_x64_windows_hotspot_21.0.12.1_1.zip"
PG_SOURCE = "https://get.enterprisedb.com/postgresql/postgresql-16.15-4-windows-x64-binaries.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

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
        raise SystemExit("the source commit could not be recorded for this build.")
    return revision


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_inputs() -> dict[str, dict[str, object]]:
    receipt: dict[str, dict[str, object]] = {}
    for name, spec in EXPECTED.items():
        path = DL / name
        if not path.is_file():
            raise SystemExit(f"missing staged archive: {path}")
        actual_size = path.stat().st_size
        if actual_size != spec["size"]:
            raise SystemExit(f"{name}: size {actual_size} != expected {spec['size']}")
        entry: dict[str, object] = {"size": actual_size}
        if name == "python-embed.zip":
            actual = md5(path)
            if actual != spec["md5"]:
                raise SystemExit(f"{name}: md5 {actual} != expected {spec['md5']}")
            entry["md5"] = actual
        else:
            actual = sha256(path)
            entry["sha256"] = actual
            if spec["sha256"] is not None and actual != spec["sha256"]:
                raise SystemExit(f"{name}: sha256 mismatch")
            if spec["sha256"] is None:
                entry["publisherHash"] = "none-published-by-EDB"
        receipt[name] = entry
    return receipt


def _file_records(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink():
            raise SystemExit(f"package input contains a symbolic link: {path}")
        if path.is_file():
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    return records




def _write_wheel_manifest(python_root: Path) -> None:
    site_packages = python_root / "Lib" / "site-packages"
    files = _file_records(site_packages)
    distributions: list[dict[str, object]] = []
    for metadata_path in sorted(site_packages.glob("*.dist-info/METADATA")):
        metadata = BytesParser().parsebytes(metadata_path.read_bytes())
        record_path = metadata_path.parent / "RECORD"
        if not record_path.is_file():
            raise SystemExit(f"installed wheel has no RECORD: {metadata_path.parent.name}")
        distribution_files: set[str] = set()
        with record_path.open(encoding="utf-8", newline="") as stream:
            for row in csv.reader(stream):
                if not row:
                    continue
                relative = Path(row[0])
                if relative.is_absolute() or ".." in relative.parts:
                    raise SystemExit(f"wheel RECORD contains an unsafe path: {metadata_path.parent.name}")
                installed = (site_packages / relative).resolve()
                if site_packages.resolve() not in installed.parents or not installed.is_file():
                    raise SystemExit(f"wheel RECORD references an absent file: {metadata_path.parent.name}")
                distribution_files.add(installed.relative_to(site_packages.resolve()).as_posix())
        license_files = sorted(
            path.relative_to(site_packages).as_posix()
            for path in metadata_path.parent.rglob("*")
            if path.is_file() and ("license" in path.name.casefold() or "copying" in path.name.casefold())
        )
        distributions.append(
            {
                "name": metadata.get("Name", metadata_path.parent.name.removesuffix(".dist-info")),
                "version": metadata.get("Version", "unknown"),
                "license": metadata.get("License-Expression") or metadata.get("License") or "not declared in wheel metadata",
                "licenseFiles": license_files,
                "files": sorted(distribution_files, key=str.casefold),
            }
        )
    if not distributions:
        raise SystemExit("no installed wheel metadata was found in the bundled site-packages")
    manifest = {
        "formatVersion": 1,
        "sourceLock": "uv.lock",
        "requirementsFile": "wheel-requirements.txt",
        "files": files,
        "distributions": distributions,
    }
    (python_root / "wheel-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _write_update_trust_module(*, release_eligible: bool = False) -> tuple[Path, str | None]:
    encoded = os.environ.get("PROJECTA_UPDATE_PUBLIC_KEY_B64") if release_eligible else None
    if encoded:
        try:
            public_key = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise SystemExit("PROJECTA_UPDATE_PUBLIC_KEY_B64 is not valid base64") from error
        if len(public_key) != 32:
            raise SystemExit("PROJECTA_UPDATE_PUBLIC_KEY_B64 must encode a 32-byte Ed25519 public key")
        fingerprint = hashlib.sha256(public_key).hexdigest()
        source = f"PUBLIC_KEY_B64 = {encoded!r}\n"
    else:
        fingerprint = None
        source = "PUBLIC_KEY_B64 = None\n"
    trust_dir = ROOT / "build" / "native-update-trust"
    trust_dir.mkdir(parents=True, exist_ok=True)
    (trust_dir / "_projecta_update_trust.py").write_text(source, encoding="utf-8")
    return trust_dir, fingerprint

def _load_release_signing_configuration(
    package: Path,
    archive: Path,
) -> dict[str, object]:
    required = (
        "PROJECTA_UPDATE_SIGNING_KEY_PATH",
        "PROJECTA_UPDATE_PUBLIC_KEY_B64",
        "PROJECTA_AUTHENTICODE_THUMBPRINT",
        "PROJECTA_AUTHENTICODE_TIMESTAMP_URL",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"owner release signing identity is incomplete; missing settings: {missing}")
    key_path = Path(os.environ["PROJECTA_UPDATE_SIGNING_KEY_PATH"]).expanduser().resolve()
    package_path = package.resolve()
    archive_path = archive.resolve()
    if (
        key_path.is_relative_to(ROOT.resolve())
        or key_path.is_relative_to(package_path)
        or key_path == archive_path
    ):
        raise SystemExit("the owner Ed25519 private key must remain outside the repository, package, and archive.")
    if not key_path.is_file():
        raise SystemExit("the configured owner Ed25519 private-key file is unavailable.")
    try:
        from cryptography.exceptions import UnsupportedAlgorithm
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        password = os.environ.get("PROJECTA_UPDATE_SIGNING_KEY_PASSWORD")
        private_key = serialization.load_pem_private_key(
            key_path.read_bytes(),
            password=password.encode("utf-8") if password is not None else None,
        )
    except (OSError, TypeError, ValueError, UnsupportedAlgorithm) as error:
        raise SystemExit("the configured owner Ed25519 private key could not be loaded.") from error
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit("the configured owner update-signing key must be Ed25519.")
    try:
        encoded_public_key = os.environ["PROJECTA_UPDATE_PUBLIC_KEY_B64"]
        public_key = base64.b64decode(encoded_public_key, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise SystemExit("PROJECTA_UPDATE_PUBLIC_KEY_B64 is invalid.") from error
    from cryptography.hazmat.primitives import serialization

    derived_public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    if len(public_key) != 32 or public_key != derived_public_key:
        raise SystemExit("the owner Ed25519 public trust anchor does not match the private signing key.")

    thumbprint = re.sub(r"\s+", "", os.environ["PROJECTA_AUTHENTICODE_THUMBPRINT"]).upper()
    if re.fullmatch(r"[0-9A-F]{40}", thumbprint) is None:
        raise SystemExit("PROJECTA_AUTHENTICODE_THUMBPRINT must be a 40-digit SHA-1 certificate thumbprint.")
    timestamp_url = os.environ["PROJECTA_AUTHENTICODE_TIMESTAMP_URL"]
    timestamp = urlparse(timestamp_url)
    if (
        timestamp.scheme != "https"
        or not timestamp.hostname
        or timestamp.username
        or timestamp.password
        or timestamp.query
        or timestamp.fragment
    ):
        raise SystemExit("PROJECTA_AUTHENTICODE_TIMESTAMP_URL must be an HTTPS RFC 3161 endpoint without credentials.")

    signtool_value = os.environ.get("PROJECTA_SIGNTOOL_PATH")
    signtool = signtool_value or shutil.which("signtool.exe")
    if signtool is None or not Path(signtool).is_file():
        raise SystemExit("Windows SDK SignTool is required for an owner-signed release package.")
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        raise SystemExit("PowerShell is required to validate the CurrentUser\\My code-signing identity.")
    environment = os.environ.copy()
    environment["PROJECTA_AUTHENTICODE_THUMBPRINT"] = thumbprint
    for secret_name in ("PROJECTA_UPDATE_SIGNING_KEY_PATH", "PROJECTA_UPDATE_SIGNING_KEY_PASSWORD"):
        environment.pop(secret_name, None)
    script = (
        "$ErrorActionPreference='Stop';"
        "$store=[System.Security.Cryptography.X509Certificates.X509Store]::new('My','CurrentUser');"
        "$store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly);"
        "$matches=@($store.Certificates | Where-Object { "
        "$_.Thumbprint.Replace(' ','').ToUpperInvariant() -eq $env:PROJECTA_AUTHENTICODE_THUMBPRINT });"
        "$hasPrivateKey=$false;$codeSigning=$false;$validNow=$false;$subject='';"
        "if($matches.Count -eq 1){$cert=$matches[0];$hasPrivateKey=$cert.HasPrivateKey;"
        "$subject=$cert.Subject;$validNow=([DateTime]::Now -ge $cert.NotBefore -and [DateTime]::Now -le $cert.NotAfter);"
        "foreach($extension in $cert.Extensions){if($extension.Oid.Value -eq '2.5.29.37'){"
        "foreach($oid in $extension.EnhancedKeyUsages){if($oid.Value -eq '1.3.6.1.5.5.7.3.3'){$codeSigning=$true}}}}};"
        "$store.Close();[pscustomobject]@{Count=$matches.Count;HasPrivateKey=$hasPrivateKey;"
        "CodeSigningEku=$codeSigning;ValidNow=$validNow;Subject=$subject}|ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        env=environment,
    )
    if result.returncode:
        raise SystemExit("the selected CurrentUser\\My code-signing certificate could not be validated.")
    try:
        certificate = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit("PowerShell returned invalid CurrentUser\\My certificate metadata.") from error
    if (
        not isinstance(certificate, dict)
        or certificate.get("Count") != 1
        or certificate.get("HasPrivateKey") is not True
        or certificate.get("CodeSigningEku") is not True
        or certificate.get("ValidNow") is not True
    ):
        raise SystemExit(
            "the selected CurrentUser\\My certificate must be current, contain the code-signing EKU, "
            "and have an accessible private key."
        )
    return {
        "ed25519PrivateKey": private_key,
        "publicKeyFingerprint": hashlib.sha256(public_key).hexdigest(),
        "authenticodeThumbprint": thumbprint,
        "timestampUrl": timestamp_url,
        "signToolPath": str(Path(signtool).resolve()),
        "certificateSubject": certificate["Subject"],
        "certificateStore": "CurrentUser\\My",
    }


def _sign_authenticode_images(package: Path, signing: dict[str, object]) -> dict[str, object]:
    sign_tool = str(signing["signToolPath"])
    thumbprint = str(signing["authenticodeThumbprint"])
    timestamp_url = str(signing["timestampUrl"])
    images = sorted(
        (
            path for path in package.rglob("*")
            if path.is_file() and path.suffix.casefold() in {".exe", ".dll", ".pyd"}
        ),
        key=lambda path: path.as_posix().casefold(),
    )
    if not images:
        raise SystemExit("the release package contains no signable Windows PE images.")
    environment = os.environ.copy()
    for secret_name in ("PROJECTA_UPDATE_SIGNING_KEY_PATH", "PROJECTA_UPDATE_SIGNING_KEY_PASSWORD"):
        environment.pop(secret_name, None)
    for start in range(0, len(images), 24):
        batch = images[start : start + 24]
        result = subprocess.run(
            [
                sign_tool,
                "sign",
                "/as",
                "/s",
                "My",
                "/sha1",
                thumbprint,
                "/fd",
                "SHA256",
                "/tr",
                timestamp_url,
                "/td",
                "SHA256",
                "/u",
                "1.3.6.1.5.5.7.3.3",
                *(str(path) for path in batch),
            ],
            capture_output=True,
            text=True,
            env=environment,
        )
        if result.returncode:
            raise SystemExit("SignTool failed to sign every PE image with the owner CurrentUser\\My certificate.")
    for start in range(0, len(images), 24):
        batch = images[start : start + 24]
        result = subprocess.run(
            [
                sign_tool,
                "verify",
                "/pa",
                "/all",
                "/tw",
                *(str(path) for path in batch),
            ],
            capture_output=True,
            text=True,
            env=environment,
        )
        if result.returncode:
            raise SystemExit("SignTool could not verify every PE signature and timestamp in the release package.")
    return {
        "algorithm": "Authenticode-SHA256",
        "certificateThumbprint": thumbprint,
        "certificateSubject": signing["certificateSubject"],
        "certificateStore": signing["certificateStore"],
        "timestampAuthority": timestamp_url,
        "signedImageCount": len(images),
        "verifiedImageCount": len(images),
        "sourceSignaturesPreserved": True,
    }


def _write_ed25519_manifest_signature(package: Path, private_key: object) -> str:
    from cryptography.hazmat.primitives import serialization

    manifest_bytes = (package / "runtime-manifest.json").read_bytes()
    signature = private_key.sign(manifest_bytes)
    public_key = private_key.public_key()
    public_key.verify(signature, manifest_bytes)
    if len(signature) != 64:
        raise SystemExit("the owner Ed25519 signer produced an invalid signature length.")
    encoded_signature = base64.b64encode(signature) + b"\n"
    signature_path = package / "runtime-manifest.sig"
    signature_path.write_bytes(encoded_signature)
    if base64.b64decode(signature_path.read_bytes().strip(), validate=True) != signature:
        raise SystemExit("the detached Ed25519 package signature could not be read back.")
    public_bytes = public_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(public_bytes).hexdigest()

def _freeze_launcher(package: Path, trust_dir: Path) -> None:
    try:
        import PyInstaller
    except (ImportError, RuntimeError) as error:
        raise SystemExit("PyInstaller 6.22.3 is required in the isolated build environment") from error
    if PyInstaller.__version__ != PYINSTALLER_VERSION:
        raise SystemExit(f"PyInstaller {PYINSTALLER_VERSION} is required; found {PyInstaller.__version__}")
    work_root = ROOT / "build" / "native-pyinstaller"
    common = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--distpath",
        str(package),
        "--paths",
        str(trust_dir),
        "--paths",
        str(ROOT / "scripts"),
        "--collect-all",
        "cryptography",
    ]
    for name, interface, entrypoint in (
        ("ProjectaLocal", "--console", ROOT / "scripts" / "projecta_local.py"),
        ("Projecta", "--windowed", ROOT / "scripts" / "projecta_desktop.py"),
    ):
        command = [
            *common,
            interface,
            "--name",
            name,
            "--workpath",
            str(work_root / f"{name.casefold()}-work"),
            "--specpath",
            str(work_root / f"{name.casefold()}-spec"),
            str(entrypoint),
        ]
        result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
        if result.returncode:
            raise SystemExit(f"PyInstaller failed for {name}.exe: {result.stderr[-3000:] or result.stdout[-3000:]}")

class _LicenseTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.blocked:
            if tag == self.blocked[-1]:
                self.blocked.append(tag)
            return
        if tag in {"script", "style", "svg"}:
            self.blocked.append(tag)
        elif tag in {"p", "div", "pre", "h1", "h2", "h3", "li", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.blocked:
            if tag == self.blocked[-1]:
                self.blocked.pop()
            return
        if tag in {"p", "div", "pre", "h1", "h2", "h3", "li", "br"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.blocked:
            self.parts.append(data)


def _maven_runtime_dependencies(jars: list[Path] | None = None) -> dict[str, dict[str, str]]:
    maven = shutil.which("mvn")
    if maven is None:
        raise SystemExit("Maven is required to resolve versioned Java runtime POMs.")
    result = subprocess.run(
        [
            maven,
            "--offline",
            "-f",
            str(ROOT / "services" / "semantic-core" / "pom.xml"),
            "dependency:list",
            "-DincludeScope=runtime",
            "-DoutputAbsoluteArtifactFilename=true",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode:
        raise SystemExit(f"Maven could not resolve Java runtime metadata: {result.stderr[-2000:] or result.stdout[-2000:]}")

    expected = {jar.name.casefold() for jar in jars} if jars is not None else None
    resolved: dict[str, dict[str, str]] = {}
    pattern = re.compile(
        r"^\[INFO\]\s+([^:]+):([^:]+):jar:(.*?):(compile|runtime):([A-Za-z]:\\.*?\.jar)(?:\s+-- module.*)?$"
    )
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        group, artifact, version_or_classifier, scope, jar_path = match.groups()
        filename = Path(jar_path).name
        if expected is not None and filename.casefold() not in expected:
            continue
        version_parts = version_or_classifier.split(":")
        version = version_parts[-1]
        classifier = version_parts[0] if len(version_parts) == 2 else ""
        repository = Path(jar_path).parent
        for _ in range(len(group.split(".")) + 2):
            repository = repository.parent
        pom_path = repository / Path(*group.split(".")) / artifact / version / f"{artifact}-{version}.pom"
        key = filename.casefold()
        if key in resolved:
            raise SystemExit(f"Java runtime contains ambiguous artifact filenames: {filename}")
        resolved[key] = {
            "groupId": group,
            "artifactId": artifact,
            "version": version,
            "classifier": classifier,
            "scope": scope,
            "jarPath": jar_path,
            "pomPath": str(pom_path),
        }
    if expected is not None:
        missing = sorted(expected - resolved.keys())
        if missing:
            raise SystemExit(f"Java runtime JARs lack an exact Maven runtime coordinate: {missing}")
    if not resolved:
        raise SystemExit("Maven resolved no Java runtime JARs.")
    for coordinate in resolved.values():
        if not Path(coordinate["jarPath"]).is_file() or not Path(coordinate["pomPath"]).is_file():
            raise SystemExit(f"resolved Java runtime JAR or published POM is absent: {coordinate['artifactId']}")
    return resolved


def _pom_children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if child.tag.rsplit("}", 1)[-1] == name]


def _pom_text(element: ET.Element, name: str) -> str:
    children = _pom_children(element, name)
    return (children[0].text or "").strip() if children else ""


def _license_url(name: str, url: str) -> str:
    if url:
        if url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        if url == "https://www.opensource.org/licenses/mit-license.php":
            return "https://opensource.org/license/mit/"
        return url
    fallback = {
        "apache license, version 2.0": "https://www.apache.org/licenses/LICENSE-2.0.txt",
        "apache-2.0": "https://www.apache.org/licenses/LICENSE-2.0.txt",
        "bsd 3-clause license": "https://opensource.org/license/bsd-3-clause/",
        "bsd-3-clause": "https://opensource.org/license/bsd-3-clause/",
        "mit license": "https://opensource.org/license/mit/",
        "mit": "https://opensource.org/license/mit/",
    }
    resolved = fallback.get(name.casefold())
    if resolved is None:
        raise SystemExit(f"Java POM license has no official source URL: {name}")
    return resolved


def _maven_license_metadata(pom_path: Path, repository: Path, coordinates: dict[str, str]) -> dict[str, object]:
    chain: list[dict[str, str]] = []
    visited: set[Path] = set()
    current = pom_path
    licenses: list[dict[str, str]] = []
    project_url = ""
    scm_url = ""
    for _ in range(16):
        if current in visited or not current.is_file():
            raise SystemExit(f"published Maven POM or parent is missing: {current.name}")
        visited.add(current)
        try:
            root = ET.parse(current).getroot()
        except ET.ParseError as error:
            raise SystemExit(f"published Maven POM is invalid: {current.name}") from error
        group = _pom_text(root, "groupId") or coordinates["groupId"]
        artifact = _pom_text(root, "artifactId")
        version = _pom_text(root, "version") or coordinates["version"]
        central_path = f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.pom"
        source = {
            "url": f"https://repo.maven.apache.org/maven2/{central_path}",
            "sha256": sha256(current),
        }
        chain.append(source)
        if not project_url:
            project_url = _pom_text(root, "url")
        if not scm_url:
            scm_nodes = _pom_children(root, "scm")
            if scm_nodes:
                scm_url = _pom_text(scm_nodes[0], "url") or _pom_text(scm_nodes[0], "connection")
        license_containers = _pom_children(root, "licenses")
        for container in license_containers:
            for license_node in _pom_children(container, "license"):
                name = _pom_text(license_node, "name")
                url = _pom_text(license_node, "url")
                if not name:
                    raise SystemExit(f"published Maven POM has an unnamed license: {current.name}")
                licenses.append(
                    {
                        "name": name,
                        "url": _license_url(name, url),
                        "declaredByPom": source["url"],
                        "declaredByPomSha256": source["sha256"],
                    }
                )
        if licenses:
            break
        parents = _pom_children(root, "parent")
        if not parents:
            break
        parent = parents[0]
        parent_group = _pom_text(parent, "groupId")
        parent_artifact = _pom_text(parent, "artifactId")
        parent_version = _pom_text(parent, "version")
        if not (parent_group and parent_artifact and parent_version):
            break
        current = (
            repository
            / Path(*parent_group.split("."))
            / parent_artifact
            / parent_version
            / f"{parent_artifact}-{parent_version}.pom"
        )
    if not licenses:
        raise SystemExit(f"Java dependency POM and parent chain declare no license: {pom_path.name}")
    return {
        "publishedPOM": chain[0],
        "licensePOMChain": chain,
        "projectUrl": project_url,
        "scmUrl": scm_url,
        "licenses": licenses,
    }


def _download_license_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Projecta native package license inventory"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content_type = response.headers.get_content_type()
            if not response.geturl().startswith("https://") or content_type not in {
                "text/plain",
                "text/html",
                "application/xhtml+xml",
                "application/octet-stream",
            }:
                raise SystemExit(f"license source returned an unexpected response: {url}")
            content = response.read(4 * 1024 * 1024 + 1)
    except (OSError, urllib.error.URLError) as error:
        raise SystemExit(f"official Java license text could not be retrieved: {url}") from error
    if len(content) > 4 * 1024 * 1024:
        raise SystemExit(f"official Java license text is unexpectedly large: {url}")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise SystemExit(f"official Java license text is not UTF-8: {url}") from error
    if content_type != "text/plain":
        parser = _LicenseTextParser()
        parser.feed(text)
        parser.close()
        text = "".join(parser.parts)
    text = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()).strip()
    if len(text) < 200:
        raise SystemExit(f"official Java license source contains no complete license text: {url}")
    return text + "\n"


def _store_java_license(
    notice_root: Path,
    content_paths: dict[str, str],
    *,
    name: str,
    url: str,
) -> dict[str, str]:
    content = _download_license_text(url)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    stored = content_paths.get(digest)
    if stored is None:
        stored = f"third-party-notices/{digest[:16]}-LICENSE.txt"
        (notice_root.parent / stored).write_text(content, encoding="utf-8", newline="\n")
        content_paths[digest] = stored
    return {"name": name, "sourceUrl": url, "path": stored, "sha256": digest}


def _write_java_notices(
    semantic_core: Path,
    resolved_dependencies: dict[str, dict[str, str]] | None = None,
) -> dict[str, object]:
    notice_root = semantic_core / "third-party-notices"
    notice_root.mkdir(parents=True, exist_ok=True)
    content_paths: dict[str, str] = {}
    libraries: list[dict[str, object]] = []
    jars = sorted((semantic_core / "lib").glob("*.jar"), key=lambda path: path.name.casefold())
    resolved = resolved_dependencies or _maven_runtime_dependencies(jars)
    if {jar.name.casefold() for jar in jars} != set(resolved):
        raise SystemExit("staged Java JARs do not match Maven's current runtime dependency graph.")
    for jar in jars:
        coordinate = resolved[jar.name.casefold()]
        pom_path = Path(coordinate["pomPath"])
        if not pom_path.is_file():
            raise SystemExit(f"published Maven POM is missing for {jar.name}")
        repository = Path(coordinate["jarPath"]).parent
        for _ in range(len(coordinate["groupId"].split(".")) + 2):
            repository = repository.parent
        metadata = _maven_license_metadata(pom_path, repository, coordinate)
        embedded: list[dict[str, str]] = []
        with zipfile.ZipFile(jar) as archive:
            for member in archive.namelist():
                name = Path(member).name
                folded = name.casefold()
                if not (
                    folded.startswith(("license", "notice", "copying", "dependencies"))
                    and (member.upper().startswith("META-INF/") or "/" not in member)
                ):
                    continue
                content = archive.read(member)
                digest = hashlib.sha256(content).hexdigest()
                stored = content_paths.get(digest)
                if stored is None:
                    stored = f"third-party-notices/{digest[:16]}-{name}"
                    (semantic_core / stored).write_bytes(content)
                    content_paths[digest] = stored
                embedded.append({"member": member, "path": stored, "sha256": digest})
        is_dexx_collection = (
            coordinate["groupId"] == "com.github.andrewoma.dexx"
            and coordinate["artifactId"] == "collection"
            and coordinate["version"] == "0.7"
        )
        external: list[dict[str, str]] = []
        for license_item in metadata["licenses"]:
            source_url = license_item["url"]
            if is_dexx_collection and license_item["name"].casefold() == "mit license":
                source_url = "https://raw.githubusercontent.com/andrewoma/dexx/0.7/LICENSE.txt"
            external.append(
                _store_java_license(
                    notice_root,
                    content_paths,
                    name=license_item["name"],
                    url=source_url,
                )
            )
        upstream_notices: list[dict[str, str]] = []
        if is_dexx_collection:
            notice_url = "https://raw.githubusercontent.com/andrewoma/dexx/0.7/NOTICE.txt"
            upstream_notices.append(
                _store_java_license(
                    notice_root,
                    content_paths,
                    name="Upstream NOTICE.txt",
                    url=notice_url,
                )
            )
            external.append(
                _store_java_license(
                    notice_root,
                    content_paths,
                    name="BSD-style license for Scala-derived portions",
                    url="https://raw.githubusercontent.com/andrewoma/dexx/0.7/licenses/LICENSE_Scala.txt",
                )
            )
        libraries.append(
            {
                "jar": jar.name,
                "sha256": sha256(jar),
                "coordinates": {
                    key: coordinate[key]
                    for key in ("groupId", "artifactId", "version", "classifier", "scope")
                },
                "publishedPOM": metadata["publishedPOM"],
                "licensePOMChain": metadata["licensePOMChain"],
                "projectUrl": metadata["projectUrl"],
                "scmUrl": metadata["scmUrl"],
                "licenses": metadata["licenses"],
                "externalLicenseTexts": external,
                "upstreamNotices": upstream_notices,
                "embeddedLicenseNotices": embedded,
            }
        )
    result = {
        "formatVersion": 2,
        "fusekiVersion": RUNTIME_VERSIONS["fuseki"],
        "libraries": libraries,
    }
    (semantic_core / "java-third-party-notices.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def _write_component_manifest(
    directory: Path,
    component: str,
    version: str,
    *,
    include: tuple[str, ...] = (),
) -> None:
    entries: list[dict[str, object]] = []
    roots = [directory / relative for relative in include] if include else [directory]
    for root in roots:
        if not root.is_dir():
            raise SystemExit(f"{component} manifest input is missing: {root}")
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if path.is_symlink():
                raise SystemExit(f"{component} manifest input contains a symbolic link: {path}")
            if path.is_file():
                entries.append(
                    {
                        "path": path.relative_to(directory).as_posix(),
                        "size": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                )
    entries.sort(key=lambda entry: str(entry["path"]).casefold())
    manifest = {"formatVersion": 1, "component": component, "version": version, "files": entries}
    (directory / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _write_native_dependency_manifest(package: Path) -> dict[str, object]:
    system_dlls = {
        "advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "cabinet.dll", "cfgmgr32.dll",
        "combase.dll", "comctl32.dll", "comdlg32.dll", "crypt32.dll", "dbghelp.dll",
        "dnsapi.dll", "dsound.dll", "dwrite.dll", "dwmapi.dll", "gdi32.dll", "gdi32full.dll",
        "imm32.dll", "iphlpapi.dll", "kernel32.dll", "kernelbase.dll", "msi.dll",
        "msimg32.dll", "msvcrt.dll", "mswsock.dll", "ncrypt.dll", "normaliz.dll",
        "ntdll.dll", "ole32.dll", "oleacc.dll", "oleaut32.dll", "pdh.dll", "powrprof.dll",
        "propsys.dll", "psapi.dll", "profapi.dll", "rpcrt4.dll", "sechost.dll",
        "secur32.dll", "setupapi.dll", "shell32.dll", "shlwapi.dll", "ucrtbase.dll",
        "user32.dll", "uxtheme.dll", "version.dll", "win32u.dll", "winhttp.dll",
        "winmm.dll", "winspool.drv", "winscard.dll", "wldap32.dll", "ws2_32.dll",
    }
    api_set_prefixes = ("api-ms-win-", "ext-ms-win-")
    loader_apis = {
        "adddlldirectory",
        "getmodulehandlea",
        "getmodulehandlew",
        "getprocaddress",
        "loadlibrarya",
        "loadlibraryex",
        "loadlibraryexa",
        "loadlibraryexw",
        "loadlibraryw",
        "ldrloaddll",
        "setdefaultdlldirectories",
    }
    ascii_module_literal = re.compile(
        rb"(?i)(?<![A-Z0-9_.+-])([A-Z0-9_.+-]{1,120}\.(?:DLL|PYD))(?![A-Z0-9_.+-])"
    )
    wide_module_literal = re.compile(
        rb"(?i)((?:[A-Z0-9_.+-]\x00){1,120}\.\x00(?:D\x00L\x00L\x00|P\x00Y\x00D\x00))"
    )
    runtime_root = package / "runtime"
    module_paths: dict[str, list[str]] = {}
    images = sorted(
        (
            path for path in runtime_root.rglob("*")
            if path.is_file() and path.suffix.casefold() in {".exe", ".dll", ".pyd"}
        ),
        key=lambda path: path.as_posix().casefold(),
    )
    for path in images:
        module_paths.setdefault(path.name.casefold(), []).append(path.relative_to(package).as_posix())
    bundled_modules = set(module_paths)

    def classify_module(name: str) -> str:
        folded = name.casefold()
        if folded in bundled_modules:
            return "appLocal"
        if folded in system_dlls or folded.startswith(api_set_prefixes):
            return "windows11X64OSBaseline"
        return "unresolved"

    entries: list[dict[str, object]] = []
    unresolved: set[str] = set()
    unverified_dynamic_candidates: set[str] = set()
    for image in images:
        data = image.read_bytes()
        if len(data) < 0x40 or data[:2] != b"MZ":
            continue
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise SystemExit(f"invalid PE image in staged runtime: {image}")
        machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
        if machine != 0x8664:
            raise SystemExit(f"staged runtime contains a non-x64 PE image: {image}")
        section_count = struct.unpack_from("<H", data, pe_offset + 6)[0]
        optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
        optional = pe_offset + 24
        if optional + optional_size > len(data):
            raise SystemExit(f"truncated PE optional header: {image}")
        magic = struct.unpack_from("<H", data, optional)[0]
        if magic == 0x20B:
            directory_offset, directory_count_offset = 112, 108
            image_base = struct.unpack_from("<Q", data, optional + 24)[0]
            thunk_size, ordinal_mask = 8, 1 << 63
        elif magic == 0x10B:
            directory_offset, directory_count_offset = 96, 92
            image_base = struct.unpack_from("<I", data, optional + 28)[0]
            thunk_size, ordinal_mask = 4, 1 << 31
        else:
            raise SystemExit(f"unsupported PE optional header: {image}")
        if optional_size < directory_count_offset + 4:
            raise SystemExit(f"truncated PE data-directory header: {image}")
        directory_count = struct.unpack_from("<I", data, optional + directory_count_offset)[0]
        directory_base = optional + directory_offset
        section_table = optional + optional_size
        if section_table + section_count * 40 > len(data):
            raise SystemExit(f"truncated PE section table: {image}")
        sections: list[tuple[int, int, int, int]] = []
        for index in range(section_count):
            section = section_table + index * 40
            virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", data, section + 8)
            sections.append((virtual_address, max(virtual_size, raw_size), raw_size, raw_offset))

        def directory(index: int) -> tuple[int, int]:
            if directory_count <= index:
                return 0, 0
            position = directory_base + index * 8
            if position + 8 > optional + optional_size:
                raise SystemExit(f"truncated PE data directory: {image}")
            return struct.unpack_from("<II", data, position)

        def rva_offset(rva: int) -> int:
            for virtual_address, span, raw_size, raw_offset in sections:
                if virtual_address <= rva < virtual_address + span:
                    offset = raw_offset + rva - virtual_address
                    if offset < raw_offset + raw_size:
                        return offset
            raise SystemExit(f"PE import RVA is outside its sections: {image}")

        def c_string(rva: int) -> str:
            offset = rva_offset(rva)
            end = data.find(b"\0", offset)
            if end < 0:
                raise SystemExit(f"unterminated PE import name: {image}")
            try:
                return data[offset:end].decode("ascii").casefold()
            except UnicodeDecodeError as error:
                raise SystemExit(f"non-ASCII PE import name: {image}") from error

        def delay_pointer_to_rva(value: int, attributes: int) -> int:
            if not value:
                return 0
            if attributes & 1:
                return value
            if value < image_base:
                raise SystemExit(f"invalid VA-based PE delay import: {image}")
            return value - image_base

        def imported_functions(table_rva: int, delay_attributes: int | None = None) -> set[str]:
            if not table_rva:
                return set()
            table_offset = rva_offset(table_rva)
            result: set[str] = set()
            for index in range(len(data) // thunk_size):
                position = table_offset + index * thunk_size
                if position + thunk_size > len(data):
                    raise SystemExit(f"truncated PE import thunk table: {image}")
                value = int.from_bytes(data[position : position + thunk_size], "little")
                if value == 0:
                    return result
                if value & ordinal_mask:
                    continue
                name_rva = value if delay_attributes is None else delay_pointer_to_rva(value, delay_attributes)
                name_offset = rva_offset(name_rva)
                if name_offset + 2 >= len(data):
                    raise SystemExit(f"truncated PE import symbol: {image}")
                end = data.find(b"\0", name_offset + 2)
                if end < 0:
                    raise SystemExit(f"unterminated PE import symbol: {image}")
                try:
                    result.add(data[name_offset + 2 : end].decode("ascii").casefold())
                except UnicodeDecodeError as error:
                    raise SystemExit(f"non-ASCII PE import symbol: {image}") from error
            raise SystemExit(f"unterminated PE import thunk table: {image}")

        imports: set[str] = set()
        delay_imports: set[str] = set()
        symbols: set[str] = set()
        import_rva, import_size = directory(1)
        if import_rva and import_size:
            descriptor = rva_offset(import_rva)
            end = min(descriptor + import_size, len(data))
            terminated = False
            for offset in range(descriptor, end - 19, 20):
                original_thunk, timestamp, forwarder, name_rva, first_thunk = struct.unpack_from("<IIIII", data, offset)
                if not any((original_thunk, timestamp, forwarder, name_rva, first_thunk)):
                    terminated = True
                    break
                imports.add(c_string(name_rva))
                symbols.update(imported_functions(original_thunk or first_thunk))
            if not terminated:
                raise SystemExit(f"unterminated PE import directory: {image}")

        delay_rva, delay_size = directory(13)
        if delay_rva and delay_size:
            descriptor = rva_offset(delay_rva)
            end = min(descriptor + delay_size, len(data))
            terminated = False
            for offset in range(descriptor, end - 31, 32):
                fields = struct.unpack_from("<IIIIIIII", data, offset)
                if not any(fields):
                    terminated = True
                    break
                attributes, name_pointer, _, _, int_pointer, _, _, _ = fields
                if attributes & ~1:
                    raise SystemExit(f"unsupported PE delay-import attributes: {image}")
                name_rva = delay_pointer_to_rva(name_pointer, attributes)
                thunk_rva = delay_pointer_to_rva(int_pointer, attributes)
                delay_imports.add(c_string(name_rva))
                symbols.update(imported_functions(thunk_rva, attributes))
            if not terminated:
                raise SystemExit(f"unterminated PE delay-import directory: {image}")

        all_imports = imports | delay_imports
        module_classifications = [
            {"name": name, "classification": classify_module(name)}
            for name in sorted(all_imports)
        ]
        missing = sorted(
            name for name in all_imports
            if classify_module(name) == "unresolved"
        )
        unresolved.update(f"{image.relative_to(package).as_posix()}:{name}" for name in missing)
        dynamic_apis = sorted(symbols & loader_apis)
        dynamic_candidates: dict[str, str] = {}
        if dynamic_apis:
            for match in ascii_module_literal.finditer(data):
                name = match.group(1).decode("ascii").casefold()
                classification = classify_module(name)
                dynamic_candidates[name] = (
                    "unverifiedDynamicStringCandidate" if classification == "unresolved" else classification
                )
            for match in wide_module_literal.finditer(data):
                name = match.group(1).decode("utf-16le").casefold()
                name = name.replace("\\", "/").rsplit("/", 1)[-1]
                classification = classify_module(name)
                dynamic_candidates[name] = (
                    "unverifiedDynamicStringCandidate" if classification == "unresolved" else classification
                )
        unverified_names = sorted(
            name
            for name, classification in dynamic_candidates.items()
            if classification == "unverifiedDynamicStringCandidate"
        )
        unverified_dynamic_candidates.update(
            f"{image.relative_to(package).as_posix()}:{name}"
            for name in unverified_names
        )
        entries.append(
            {
                "path": image.relative_to(package).as_posix(),
                "sha256": sha256(image),
                "staticImports": sorted(imports),
                "delayImports": sorted(delay_imports),
                "importedSymbols": sorted(symbols),
                "dynamicLoaderApis": dynamic_apis,
                "dynamicModuleCandidates": [
                    {"name": name, "classification": classification}
                    for name, classification in sorted(dynamic_candidates.items())
                ],
                "importClassifications": module_classifications,
                "unresolved": missing,
                "unverifiedDynamicStringCandidates": unverified_names,
            }
        )
    manifest = {
        "formatVersion": 2,
        "runtimeVersions": dict(RUNTIME_VERSIONS),
        "minimumHost": {
            "operatingSystem": "Windows 11",
            "minimumBuild": 22000,
            "architecture": "x64",
        },
        "resolutionClasses": {
            "appLocal": "A DLL/PYD/EXE is present in the recursively staged runtime tree.",
            "windows11X64OSBaseline": "Windows system DLL, UCRT, or OS API-set contract for the declared baseline.",
            "unresolved": "Static or delay import not found in the package or declared Windows 11 x64 OS/API-set baseline.",
            "unverifiedDynamicStringCandidate": "DLL-like string in a loader-API importing image; not proven to be passed to a loader without code-flow analysis.",
        },
        "windowsSystemDlls": sorted(system_dlls),
        "apiSetPrefixes": list(api_set_prefixes),
        "bundledModules": {
            name: sorted(paths, key=str.casefold)
            for name, paths in sorted(module_paths.items())
        },
        "images": entries,
        "unresolvedDependencies": sorted(unresolved),
        "unverifiedDynamicStringCandidates": sorted(unverified_dynamic_candidates),
    }
    (package / "runtime" / "native-dependency-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    if unresolved:
        raise SystemExit(f"staged native images import unbundled dependencies: {sorted(unresolved)}")
    return manifest






def stage_python(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DL / "python-embed.zip") as archive:
        archive.extractall(dest)
    pth = dest / "python312._pth"
    text = pth.read_text(encoding="utf-8")
    if "import site" not in text:
        text = text.rstrip("\n") + "\nimport site\n"
    else:
        text = text.replace("#import site", "import site")
    if "Lib\\site-packages" not in text and "Lib/site-packages" not in text:
        text = text.rstrip("\n") + "\nLib\\site-packages\n"
    pth.write_text(text, encoding="utf-8")
    (dest / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)
    # Locked API dependencies as Windows wheels into the bundle (no pip at runtime).
    export = subprocess.run(
        ["uv", "export", "--project", "apps/api", "--format", "requirements.txt",
         "--no-hashes", "--no-header", "--no-annotate", "--no-default-groups"],
        capture_output=True, text=True, cwd=ROOT,
    )
    if export.returncode != 0:
        raise SystemExit(f"uv export failed: {export.stderr[:500]}")
    lines = [
        line.strip() for line in export.stdout.splitlines()
        if line.strip() and not line.strip().startswith("-e ") and not line.strip().startswith("#")
    ]
    req_file = dest / "wheel-requirements.txt"
    req_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    shutil.copy2(ROOT / "apps" / "api" / "uv.lock", dest / "uv.lock")
    # Wheel selection uses the CPython 3.12 Windows ABI; the shipped interpreter is pinned to 3.12.10.
    install = subprocess.run(
        ["uv", "pip", "install", "--python",
         "cpython-3.12.12-windows-x86_64-none",
         "--only-binary", ":all:",
         "--target", str(dest / "Lib" / "site-packages"),
         "-r", str(req_file)],
        capture_output=True, text=True, cwd=ROOT,
    )
    if install.returncode != 0:
        raise SystemExit(f"uv pip install failed: {install.stderr[-2000:]}")
    _write_wheel_manifest(dest)


def stage_java(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DL / "jre.zip") as archive:
        names = archive.namelist()
        top = sorted({n.split("/")[0] for n in names if "/" in n})[0]
        for member in names:
            if member.endswith("/"):
                continue
            relative = Path(member).relative_to(top)
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as out:
                shutil.copyfileobj(source, out)
    java_exe = dest / "bin" / "java.exe"
    if not java_exe.is_file():
        raise SystemExit("staged JRE is missing bin/java.exe")


def stage_postgres(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    tmp = ROOT / "build" / "pg-extract"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(DL / "pg-binaries.zip") as archive:
        archive.extractall(tmp)
    server = tmp / "pgsql"
    if not (server / "bin" / "initdb.exe").is_file():
        raise SystemExit("staged PostgreSQL archive is missing pgsql/bin/initdb.exe")
    optional_extensions = (
        "plperl",
        "bool_plperl",
        "hstore_plperl",
        "jsonb_plperl",
        "plpython3",
        "hstore_plpython3",
        "jsonb_plpython3",
        "ltree_plpython3",
        "pltcl",
    )

    def ignore_optional_extensions(directory: str, names: list[str]) -> set[str]:
        relative = Path(directory).relative_to(server)
        relative_parts = tuple(part.casefold() for part in relative.parts)
        if relative_parts == ("lib",):
            return {
                name for name in names
                if name.casefold() == "pkgconfig"
                or Path(name).suffix.casefold() in {".lib", ".a"}
                or Path(name).stem.casefold().startswith(optional_extensions)
            }
        if relative_parts == ("share", "extension"):
            return {name for name in names if name.casefold().startswith(optional_extensions)}
        return set()

    dest.mkdir(parents=True, exist_ok=True)
    for directory in ("bin", "lib", "share"):
        source = server / directory
        if not source.is_dir():
            raise SystemExit(f"staged PostgreSQL archive is missing pgsql/{directory}")
        shutil.copytree(source, dest / directory, ignore=ignore_optional_extensions)
    for name in ("server_license.txt", "commandlinetools_3rd_party_licenses.txt"):
        license_source = server / name
        if not license_source.is_file():
            raise SystemExit(f"staged PostgreSQL archive is missing {name}")
        shutil.copy2(license_source, dest / name)
    for name in ("initdb.exe", "postgres.exe", "pg_ctl.exe", "createdb.exe", "pg_isready.exe", "psql.exe"):
        if not (dest / "bin" / name).is_file():
            raise SystemExit(f"staged PostgreSQL is missing bin/{name}")
    shutil.rmtree(tmp, ignore_errors=True)


def stage_project(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    api_src = ROOT / "apps" / "api" / "src" / "projecta_api"
    api_dest = dest / "api" / "src" / "projecta_api"
    shutil.copytree(api_src, api_dest)
    shutil.copy2(ROOT / "apps" / "api" / "alembic.ini", dest / "api" / "alembic.ini")
    shutil.copytree(ROOT / "apps" / "api" / "alembic", dest / "api" / "alembic")
    core_classes = ROOT / "services" / "semantic-core" / "target" / "classes"
    core_lib = ROOT / "services" / "semantic-core" / "target" / "lib"
    if not (core_classes / "org" / "projecta" / "semanticcore" / "SemanticCoreApplication.class").is_file():
        raise SystemExit("Maven classes are missing; run mvn package first")
    fuseki_jar = core_lib / f"jena-fuseki-main-{RUNTIME_VERSIONS['fuseki']}.jar"
    if not fuseki_jar.is_file():
        raise SystemExit("Pinned Fuseki server runtime jar is absent from target/lib")
    shutil.copytree(core_classes, dest / "semantic-core" / "classes")
    semantic_core = dest / "semantic-core"
    lib_dest = semantic_core / "lib"
    lib_dest.mkdir()
    runtime_dependencies = _maven_runtime_dependencies()
    for coordinate in runtime_dependencies.values():
        shutil.copy2(coordinate["jarPath"], lib_dest / Path(coordinate["jarPath"]).name)
    _write_java_notices(semantic_core, runtime_dependencies)
    _write_component_manifest(
        semantic_core,
        "semantic-core",
        RUNTIME_VERSIONS["fuseki"],
        include=("classes", "lib"),
    )
    # Ontology: full modules + shapes (packaged read-only input for bootstrap + Core).
    shutil.copytree(ROOT / "ontology", dest / "ontology",
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    _write_component_manifest(dest / "ontology", "ontology", APP_VERSION)
    # Fuseki template: adapt the shipped Docker config path to a package template.
    template_src = ROOT / "infra" / "docker" / "fuseki" / "config" / "fuseki-config.ttl"
    template = template_src.read_text(encoding="utf-8")
    if template.count('"/var/lib/fuseki/databases/projecta"') != 1:
        raise SystemExit("shipped fuseki config template anchor changed")
    (dest / "fuseki-config.template.ttl").write_text(template, encoding="utf-8")
    (dest / "fuseki-config.ttl").write_text(template, encoding="utf-8")
    scripts = dest / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "bootstrap_fuseki.py", scripts / "bootstrap_fuseki.py")
    shutil.copy2(ROOT / "scripts" / "projecta_local.py", scripts / "projecta_local.py")
    web_src = ROOT / "apps" / "web" / "dist"
    if not (web_src / "index.html").is_file():
        raise SystemExit("compiled SPA is missing; build apps/web first")
    shutil.copytree(web_src, dest / "web")
    _write_component_manifest(dest / "web", "web", APP_VERSION)


def _verify_app_local_vc_runtime(
    package: Path,
    receipt: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    vc_runtime_names = {
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "msvcp140_atomic_wait.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
    }
    runtime_root = package / "runtime"
    files = sorted(
        (
            path for path in runtime_root.rglob("*")
            if path.is_file() and path.name.casefold() in vc_runtime_names
        ),
        key=lambda path: path.as_posix().casefold(),
    )
    if not files:
        raise SystemExit("no app-local Microsoft VC runtime DLLs were found in the staged package.")
    if os.name != "nt":
        raise SystemExit("Authenticode verification of app-local VC runtime DLLs requires Windows.")

    import ctypes
    import uuid
    from ctypes import wintypes

    class Guid(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

        @classmethod
        def from_uuid(cls, value: str) -> Guid:
            result = cls()
            ctypes.memmove(ctypes.byref(result), uuid.UUID(value).bytes_le, 16)
            return result

    class FileInfo(ctypes.Structure):
        _fields_ = [
            ("cbStruct", wintypes.DWORD),
            ("pcwszFilePath", wintypes.LPCWSTR),
            ("hFile", wintypes.HANDLE),
            ("pgKnownSubject", ctypes.POINTER(Guid)),
        ]

    class TrustData(ctypes.Structure):
        _fields_ = [
            ("cbStruct", wintypes.DWORD),
            ("pPolicyCallbackData", ctypes.c_void_p),
            ("pSIPClientData", ctypes.c_void_p),
            ("dwUIChoice", wintypes.DWORD),
            ("fdwRevocationChecks", wintypes.DWORD),
            ("dwUnionChoice", wintypes.DWORD),
            ("pFile", ctypes.POINTER(FileInfo)),
            ("dwStateAction", wintypes.DWORD),
            ("hWVTStateData", wintypes.HANDLE),
            ("pwszURLReference", wintypes.LPWSTR),
            ("dwProvFlags", wintypes.DWORD),
            ("dwUIContext", wintypes.DWORD),
            ("pSignatureSettings", ctypes.c_void_p),
        ]

    wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
    verify = wintrust.WinVerifyTrust
    verify.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(Guid),
        ctypes.POINTER(TrustData),
    ]
    verify.restype = ctypes.c_long
    action = Guid.from_uuid("00AAC56B-CD44-11d0-8CC2-00C04FC295EE")
    for path in files:
        file_info = FileInfo(ctypes.sizeof(FileInfo), str(path), None, None)
        trust_data = TrustData()
        trust_data.cbStruct = ctypes.sizeof(TrustData)
        trust_data.dwUIChoice = 2
        trust_data.fdwRevocationChecks = 0
        trust_data.dwUnionChoice = 1
        trust_data.pFile = ctypes.pointer(file_info)
        trust_data.dwStateAction = 0
        trust_data.dwProvFlags = 0x1000
        status = verify(None, ctypes.byref(action), ctypes.byref(trust_data))
        if status != 0:
            raise SystemExit(
                f"app-local VC runtime DLL failed WinVerifyTrust: "
                f"{path.relative_to(package).as_posix()} (0x{status & 0xFFFFFFFF:08x})"
            )

    powershell = shutil.which("powershell.exe")
    if powershell is None:
        raise SystemExit("PowerShell is required to read signed VC runtime publisher/version metadata.")
    environment = os.environ.copy()
    for secret_name in ("PROJECTA_UPDATE_SIGNING_KEY_PATH", "PROJECTA_UPDATE_SIGNING_KEY_PASSWORD"):
        environment.pop(secret_name, None)
    environment["PROJECTA_VC_RUNTIME_PATHS_JSON"] = json.dumps([str(path) for path in files])
    script = (
        "$paths=ConvertFrom-Json $env:PROJECTA_VC_RUNTIME_PATHS_JSON; "
        "$items=@(foreach($path in $paths){"
        "$v=[System.Diagnostics.FileVersionInfo]::GetVersionInfo($path);"
        "$c=[System.Security.Cryptography.X509Certificates.X509Certificate]::CreateFromSignedFile($path);"
        "[pscustomobject]@{Path=$path;Company=$v.CompanyName;OriginalFilename=$v.OriginalFilename;"
        "FileVersion=$v.FileVersion;ProductVersion=$v.ProductVersion;Signer=$c.Subject;"
        "Thumbprint=$c.GetCertHashString()}});"
        "ConvertTo-Json -InputObject $items -Depth 4 -Compress"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        env=environment,
    )
    if result.returncode:
        raise SystemExit("PowerShell could not read signed VC runtime publisher/version metadata.")
    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit("PowerShell returned invalid signed VC runtime metadata.") from error
    if not isinstance(metadata, list):
        raise SystemExit("PowerShell returned an incomplete signed VC runtime inventory.")
    metadata_by_path = {
        Path(item["Path"]).resolve().as_posix().casefold(): item
        for item in metadata
        if isinstance(item, dict) and isinstance(item.get("Path"), str)
    }
    source_archives = {
        "python": ("python-embed.zip", PYTHON_SOURCE),
        "java": ("jre.zip", JRE_SOURCE),
        "postgresql": ("pg-binaries.zip", PG_SOURCE),
    }
    inventory: list[dict[str, object]] = []
    for path in files:
        item = metadata_by_path.get(path.resolve().as_posix().casefold())
        if item is None:
            raise SystemExit(f"VC runtime publisher/version metadata is missing: {path.name}")
        if (
            item.get("Company") != "Microsoft Corporation"
            or item.get("OriginalFilename", "").casefold() != path.name.casefold()
            or "O=Microsoft Corporation" not in item.get("Signer", "")
        ):
            raise SystemExit(f"app-local VC runtime publisher is not Microsoft: {path.name}")
        component = path.relative_to(runtime_root).parts[0].casefold()
        source = source_archives.get(component)
        if source is None:
            raise SystemExit(f"app-local VC runtime has no staged source archive mapping: {path.name}")
        archive_name, source_url = source
        input_record = receipt[archive_name]
        hash_key = "sha256" if "sha256" in input_record else "md5"
        inventory.append(
            {
                "path": path.relative_to(package).as_posix(),
                "sha256": sha256(path),
                "fileVersion": item["FileVersion"],
                "productVersion": item["ProductVersion"],
                "company": item["Company"],
                "signerSubject": item["Signer"],
                "signerThumbprint": item["Thumbprint"],
                "authenticodeStatus": "Valid",
                "verification": "WinVerifyTrust Default Authenticode policy; revocation checks disabled",
                "sourceArchive": archive_name,
                "sourceArchiveUrl": source_url,
                "sourceArchiveHashAlgorithm": hash_key.upper().replace("SHA", "SHA-"),
                "sourceArchiveHash": input_record[hash_key],
            }
        )
    (runtime_root / "vc-runtime-inventory.json").write_text(
        json.dumps(
            {
                "formatVersion": 1,
                "deploymentMethod": "appLocal",
                "separateRedistributableInstallerIncluded": False,
                "files": inventory,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return inventory


def write_notices(
    package: Path,
    receipt: dict[str, dict[str, object]],
    *,
    release_eligible: bool = False,
    unsigned_pre_release_test: bool = False,
    installer_tool_notice: Path | None = None,
) -> list[str]:
    wheel_manifest = json.loads(
        (package / "runtime" / "python" / "wheel-manifest.json").read_text(encoding="utf-8")
    )
    java_manifest = json.loads(
        (package / "projecta" / "semantic-core" / "java-third-party-notices.json").read_text(encoding="utf-8")
    )
    native_manifest = json.loads(
        (package / "runtime" / "native-dependency-manifest.json").read_text(encoding="utf-8")
    )
    vc_manifest = json.loads(
        (package / "runtime" / "vc-runtime-inventory.json").read_text(encoding="utf-8")
    )
    app_local_vc = vc_manifest["files"]
    java_libraries = java_manifest["libraries"]
    java_unclassified = [
        library["jar"]
        for library in java_libraries
        if not library["licenses"] or not library["externalLicenseTexts"]
    ]
    if java_unclassified:
        raise SystemExit(f"Java runtime dependencies lack versioned license text: {java_unclassified}")

    if unsigned_pre_release_test and (
        APP_VERSION != UNSIGNED_PRE_RELEASE_VERSION or release_eligible or installer_tool_notice is None
    ):
        raise SystemExit("the unsigned pre-release notice is restricted to the authorized 0.7.0 installer build.")
    lines = [
        "# Third-party runtime notices",
        "",
        (
            "Owner-signed release package. This inventory records input provenance and indexes"
            if release_eligible
            else (
                "Owner-authorized unsigned 0.7.0 test pre-release; publisher identity is unverified."
                if unsigned_pre_release_test
                else "Host-validation-only bundle. This inventory records input provenance and indexes"
            )
        ),
        "This inventory records input provenance and indexes included license/notice files; it is not a legal review.",
        (
            "Unsigned pre-release exception is limited to Projecta 0.7.0 test distribution; this is not a signed release."
            if unsigned_pre_release_test
            else "This package status is not owner approval."
        ),
        "",
        f"- CPython {RUNTIME_VERSIONS['python']} embeddable (x64): {PYTHON_SOURCE}",
        f"  MD5 {receipt['python-embed.zip']['md5']}; source metadata links are published at python.org.",
        "  Python Software Foundation License text is included at runtime/python/LICENSE.txt.",
        f"- Eclipse Temurin JRE {RUNTIME_VERSIONS['java']} (x64): {JRE_SOURCE}",
        f"  SHA-256 {receipt['jre.zip']['sha256']}; Adoptium release metadata and legal/ files are included.",
        "  GPLv2 with Classpath Exception.",
        f"- EDB PostgreSQL {RUNTIME_VERSIONS['postgresql']} Windows x64 runtime: {PG_SOURCE}",
        f"  Computed SHA-256 {receipt['pg-binaries.zip']['sha256']}; EDB did not publish a hash for this archive.",
        "  Server license and command-line third-party license texts are in",
        "  runtime/postgresql/server_license.txt and commandlinetools_3rd_party_licenses.txt.",
        "  pgAdmin 4, StackBuilder, headers/static libraries, and optional PL/Perl, PL/Python, and PL/Tcl",
        "  are omitted; the Projecta local database path uses PostgreSQL core, PL/pgSQL, and client tools.",
        f"- Apache Jena/Fuseki {RUNTIME_VERSIONS['fuseki']}: {len(java_libraries)} exact Maven runtime JARs",
        "  are indexed with versioned coordinates, published POM/parent hashes, project sources, and",
        "  full official license text URLs and hashes in projecta/semantic-core/java-third-party-notices.json.",
        "  License text and upstream attribution files are bundled under projecta/semantic-core/third-party-notices/.",
        f"- Bundled Python wheels from apps/api/uv.lock: {len(wheel_manifest['distributions'])} distributions.",
        "  Exact lock, generated requirements, hashes, per-wheel files, and available license metadata/text",
        "  are in runtime/python/uv.lock, wheel-requirements.txt, and wheel-manifest.json.",
        "- App-local Microsoft VC runtime DLLs with Authenticode-valid signatures:",
        *(
            f"  - {item['path']} | {item['fileVersion']} | {item['signerSubject']}"
            for item in app_local_vc
        ),
        "  Source archive URLs/hashes and per-file SHA-256 values are in runtime/vc-runtime-inventory.json.",
        "  The package includes no separate Visual C++ Redistributable installer. App-local deployment is",
        "  permitted only under applicable Visual Studio redistribution terms; owner licensing approval is required.",
        "  Microsoft deployment guidance: https://learn.microsoft.com/en-us/cpp/windows/choosing-a-deployment-method?view=msvc-170",
        "- Recursive x64 PE static/delay import results, app-local module paths, the Windows 11 x64 OS/API-set",
        "  baseline, and dynamic loader API/string candidates are recorded in runtime/native-dependency-manifest.json.",
        "  Unresolved static/delay imports fail the package build. DLL-like strings are candidates, not proof of",
        f"  a load call; {len(native_manifest['unverifiedDynamicStringCandidates'])} candidates need runtime path coverage,",
        "  not source-string inference.",
        "",
    ]
    if installer_tool_notice is not None:
        notice_path = package / "runtime" / "installer-tool" / "NSIS-COPYING.txt"
        notice_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(installer_tool_notice, notice_path)
        lines.extend(
            [
                f"- NSIS {NSIS_VERSION} installer engine embedded in the Windows setup executable: {NSIS_DOWNLOAD_URL}",
                f"  Computed source archive SHA-256 {NSIS_ARCHIVE_SHA256}; the official download page publishes no checksum.",
                "  The full upstream COPYING file is included at runtime/installer-tool/NSIS-COPYING.txt.",
                "",
            ]
        )
    (package / "THIRD-PARTY-NOTICES.md").write_text("\n".join(lines), encoding="utf-8")
    shutil.copy2(ROOT / "LICENSE", package / "PROJECTA-LICENSE.txt")
    return ["THIRD-PARTY-NOTICES.md"]

def write_manifest(
    package: Path,
    public_key_fingerprint: str | None,
    *,
    release_eligible: bool = False,
    unsigned_pre_release_test: bool = False,
    authenticode_signing: dict[str, object] | None = None,
) -> dict[str, object]:
    if unsigned_pre_release_test and (release_eligible or APP_VERSION != UNSIGNED_PRE_RELEASE_VERSION):
        raise SystemExit("the unsigned pre-release exception is available only for unsigned Projecta 0.7.0.")
    manifest_path = package / "runtime-manifest.json"
    manifest_path.unlink(missing_ok=True)
    (package / "runtime-manifest.sig").unlink(missing_ok=True)
    files = _file_records(package)
    java_notices = json.loads(
        (package / "projecta" / "semantic-core" / "java-third-party-notices.json").read_text(encoding="utf-8")
    )
    wheel_manifest = json.loads(
        (package / "runtime" / "python" / "wheel-manifest.json").read_text(encoding="utf-8")
    )
    notice_files = {
        "THIRD-PARTY-NOTICES.md",
        "PROJECTA-LICENSE.txt",
        "runtime/python/LICENSE.txt",
        "runtime/python/wheel-manifest.json",
        "runtime/postgresql/server_license.txt",
        "runtime/postgresql/commandlinetools_3rd_party_licenses.txt",
        "projecta/semantic-core/java-third-party-notices.json",
    }
    notice_files.add("runtime/vc-runtime-inventory.json")
    installer_notice = package / "runtime" / "installer-tool" / "NSIS-COPYING.txt"
    if unsigned_pre_release_test and not installer_notice.is_file():
        raise SystemExit("the unsigned pre-release package must include the NSIS installer license notice.")
    if installer_notice.is_file():
        notice_files.add("runtime/installer-tool/NSIS-COPYING.txt")
    notice_files.update(
        f"projecta/semantic-core/{notice['path']}"
        for library in java_notices["libraries"]
        for notice in library["embeddedLicenseNotices"]
    )
    notice_files.update(
        f"projecta/semantic-core/{license_text['path']}"
        for library in java_notices["libraries"]
        for license_text in library["externalLicenseTexts"]
    )
    notice_files.update(
        f"projecta/semantic-core/{notice['path']}"
        for library in java_notices["libraries"]
        for notice in library["upstreamNotices"]
    )
    notice_files.update(
        f"runtime/python/Lib/site-packages/{license_file}"
        for distribution in wheel_manifest["distributions"]
        for license_file in distribution["licenseFiles"]
    )
    legal_root = package / "runtime" / "java" / "legal"
    notice_files.update(
        path.relative_to(package).as_posix()
        for path in legal_root.rglob("*")
        if path.is_file()
    )
    if release_eligible and (public_key_fingerprint is None or authenticode_signing is None):
        raise SystemExit("release manifests require a pinned Ed25519 trust anchor and verified Authenticode signing.")
    if not release_eligible and authenticode_signing is not None:
        raise SystemExit("host-validation manifests cannot record release signing metadata.")
    if unsigned_pre_release_test and authenticode_signing is not None:
        raise SystemExit("unsigned pre-release manifests cannot record release signing metadata.")
    manifest = {
        "formatVersion": 1,
        "projectaVersion": APP_VERSION,
        "dataContractVersion": DATA_CONTRACT_VERSION,
        "releaseEligible": release_eligible,
        "distributionChannel": (
            "signed-release"
            if release_eligible
            else UNSIGNED_PRE_RELEASE_CHANNEL
            if unsigned_pre_release_test
            else "host-validation"
        ),
        "sourceRevision": _source_revision(),
        "signatureAlgorithm": "Ed25519",
        "publicKeyFingerprint": public_key_fingerprint,
        "authenticodeSigning": authenticode_signing,
        "runtimeVersions": dict(RUNTIME_VERSIONS),
        "noticeFiles": sorted(notice_files, key=str.casefold),
        "files": files,
    }
    if unsigned_pre_release_test:
        manifest["unsignedPreReleaseException"] = UNSIGNED_PRE_RELEASE_EXCEPTION
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def write_archive(package: Path, archive_path: Path) -> dict[str, object]:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1,
        allowZip64=True,
    ) as archive:
        for path in sorted(package.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if path.is_symlink():
                raise SystemExit(f"cannot package a linked path: {path}")
            if path.is_file():
                archive.write(path, path.relative_to(package).as_posix())
    return {"path": str(archive_path), "size": archive_path.stat().st_size, "sha256": sha256(archive_path)}


def verify_assembled(
    package: Path,
    *,
    release_eligible: bool = False,
    unsigned_pre_release_test: bool = False,
) -> None:
    required = [
        package / "runtime" / "python" / "python.exe",
        package / "runtime" / "python" / "python312._pth",
        package / "runtime" / "java" / "bin" / "java.exe",
        package / "runtime" / "postgresql" / "bin" / "initdb.exe",
        package / "runtime" / "postgresql" / "bin" / "postgres.exe",
        package / "runtime" / "postgresql" / "bin" / "pg_ctl.exe",
        package / "runtime" / "postgresql" / "bin" / "createdb.exe",
        package / "runtime" / "postgresql" / "bin" / "pg_isready.exe",
        package / "runtime" / "postgresql" / "bin" / "psql.exe",
        package / "projecta" / "api" / "src" / "projecta_api" / "main.py",
        package / "projecta" / "api" / "alembic.ini",
        package / "projecta" / "api" / "alembic" / "env.py",
        package / "projecta" / "semantic-core" / "classes" / "org" / "projecta" / "semanticcore" / "SemanticCoreApplication.class",
        package / "projecta" / "semantic-core" / "classes" / "org" / "projecta" / "semanticcore" / "LocalFusekiServer.class",
        package / "projecta" / "fuseki-config.template.ttl",
        package / "projecta" / "scripts" / "bootstrap_fuseki.py",
        package / "projecta" / "ontology" / "core.ttl",
        package / "projecta" / "web" / "index.html",
        package / "THIRD-PARTY-NOTICES.md",
        package / "projecta" / "semantic-core" / "lib" / f"jena-fuseki-main-{RUNTIME_VERSIONS['fuseki']}.jar",
        package / "runtime" / "python" / "uv.lock",
        package / "runtime" / "python" / "wheel-requirements.txt",
        package / "runtime" / "python" / "wheel-manifest.json",
        package / "runtime" / "native-dependency-manifest.json",
        package / "runtime" / "vc-runtime-inventory.json",
        package / "projecta" / "semantic-core" / "runtime-manifest.json",
        package / "projecta" / "semantic-core" / "java-third-party-notices.json",
        package / "projecta" / "ontology" / "runtime-manifest.json",
        package / "projecta" / "web" / "runtime-manifest.json",
        package / "ProjectaLocal.exe",
        package / "Projecta.exe",
        package / "PROJECTA-LICENSE.txt",
        package / "runtime-manifest.json",
    ]
    missing = [str(p.relative_to(package)) for p in required if not p.is_file()]
    if missing:
        raise SystemExit(f"assembled package is incomplete, missing: {missing}")
    native_manifest = json.loads(
        (package / "runtime" / "native-dependency-manifest.json").read_text(encoding="utf-8")
    )
    if native_manifest["unresolvedDependencies"]:
        raise SystemExit("native runtime dependency manifest contains unresolved imports")
    manifest = json.loads((package / "runtime-manifest.json").read_text(encoding="utf-8"))
    signature_path = package / "runtime-manifest.sig"
    if release_eligible:
        if (
            manifest.get("releaseEligible") is not True
            or manifest.get("distributionChannel") != "signed-release"
            or "unsignedPreReleaseException" in manifest
            or not signature_path.is_file()
        ):
            raise SystemExit("release package must have an owner-signed manifest and detached signature.")
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

            encoded_key = base64.b64decode(os.environ["PROJECTA_UPDATE_PUBLIC_KEY_B64"], validate=True)
            signature = base64.b64decode(signature_path.read_bytes().strip(), validate=True)
            Ed25519PublicKey.from_public_bytes(encoded_key).verify(
                signature,
                (package / "runtime-manifest.json").read_bytes(),
            )
        except Exception as error:
            raise SystemExit("release manifest signature verification failed.") from error
        if manifest.get("publicKeyFingerprint") != hashlib.sha256(encoded_key).hexdigest():
            raise SystemExit("release manifest fingerprint does not match its owner trust anchor.")
        signing = manifest.get("authenticodeSigning")
        if (
            not isinstance(signing, dict)
            or signing.get("signedImageCount", 0) <= 0
            or signing.get("signedImageCount") != signing.get("verifiedImageCount")
        ):
            raise SystemExit("release package does not record complete Authenticode verification.")
    elif unsigned_pre_release_test:
        if (
            APP_VERSION != UNSIGNED_PRE_RELEASE_VERSION
            or manifest.get("releaseEligible") is not False
            or manifest.get("distributionChannel") != UNSIGNED_PRE_RELEASE_CHANNEL
            or manifest.get("unsignedPreReleaseException") != UNSIGNED_PRE_RELEASE_EXCEPTION
            or manifest.get("authenticodeSigning") is not None
            or signature_path.exists()
            or not (package / "runtime" / "installer-tool" / "NSIS-COPYING.txt").is_file()
        ):
            raise SystemExit("the 0.7.0 unsigned pre-release package does not match its narrow exception contract.")
    elif (
        manifest.get("releaseEligible") is not False
        or manifest.get("distributionChannel") != "host-validation"
        or "unsignedPreReleaseException" in manifest
        or signature_path.exists()
    ):
        raise SystemExit("host-validation package must remain unsigned and non-release-eligible")


def _build_web_assets() -> None:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "npm run build"],
        capture_output=True,
        text=True,
        cwd=ROOT / "apps" / "web",
    )
    if result.returncode != 0:
        details = result.stderr[-3000:] or result.stdout[-3000:]
        raise SystemExit(f"compiled SPA build failed: {details}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a host-validation bundle, owner-authorized 0.7.0 unsigned test pre-release, or signed release."
    )
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument(
        "--release",
        action="store_true",
        help="require owner Ed25519 and CurrentUser\\My Authenticode signing identities",
    )
    parser.add_argument(
        "--unsigned-pre-release-test",
        action="store_true",
        help="build only the owner-authorized unsigned Projecta 0.7.0 test pre-release.",
    )
    parser.add_argument(
        "--installer-tool-notice",
        type=Path,
        help="upstream NSIS COPYING notice; required for the unsigned 0.7.0 pre-release build.",
    )
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args(argv)
    if args.installer_tool_notice is not None:
        installer_tool_notice = args.installer_tool_notice.expanduser()
        if not installer_tool_notice.is_absolute():
            installer_tool_notice = ROOT / installer_tool_notice
        args.installer_tool_notice = Path(os.path.abspath(installer_tool_notice))
    if args.manifest_only and (args.release or args.unsigned_pre_release_test):
        raise SystemExit("--manifest-only cannot be combined with a distributable build mode.")
    if args.release and args.unsigned_pre_release_test:
        raise SystemExit("--release and --unsigned-pre-release-test are mutually exclusive.")
    if args.unsigned_pre_release_test:
        if APP_VERSION != UNSIGNED_PRE_RELEASE_VERSION or args.installer_tool_notice is None:
            raise SystemExit("the unsigned pre-release build requires its pinned 0.7.0 version and NSIS license notice.")
        if not args.installer_tool_notice.is_file() or args.installer_tool_notice.is_symlink():
            raise SystemExit("the upstream NSIS license notice must be a regular file.")
    elif args.installer_tool_notice is not None:
        raise SystemExit("--installer-tool-notice is reserved for the unsigned 0.7.0 pre-release build.")
    receipt = verify_inputs()
    if args.manifest_only:
        print(json.dumps(receipt, indent=2))
        return 0

    package = args.output.expanduser()
    if not package.is_absolute():
        package = ROOT / package
    package = Path(os.path.abspath(package))
    output_is_default = package == OUT
    if package.is_symlink():
        raise SystemExit("the requested package output cannot be a symbolic link.")
    if args.archive is not None:
        archive_path = args.archive.expanduser()
        if not archive_path.is_absolute():
            archive_path = ROOT / archive_path
        archive_path = Path(os.path.abspath(archive_path))
    elif args.release:
        archive_path = ROOT / "build" / f"ProjectaLocal-{APP_VERSION}-win-x64-OWNER-SIGNED.zip"
    else:
        archive_path = ARCHIVE
    if archive_path.is_symlink():
        raise SystemExit("the requested package archive cannot be a symbolic link.")
    if archive_path == package or archive_path.is_relative_to(package):
        raise SystemExit("the package archive must be outside the staged package directory.")
    default_unsigned_archive = (
        not args.release
        and not args.unsigned_pre_release_test
        and args.archive is None
        and output_is_default
    )
    if archive_path.exists() and not default_unsigned_archive:
        raise SystemExit("the requested package archive already exists; existing output was left untouched.")
    signing = _load_release_signing_configuration(package, archive_path) if args.release else None
    if package.exists() and (not output_is_default or args.unsigned_pre_release_test):
        raise SystemExit("the requested package directory already exists; existing output was left untouched.")
    _build_web_assets()

    if package.exists():
        if not output_is_default:
            raise SystemExit("the requested package directory already exists; existing output was left untouched.")
        shutil.rmtree(package)
    package.mkdir(parents=True)
    stage_python(package / "runtime" / "python")
    stage_java(package / "runtime" / "java")
    stage_postgres(package / "runtime" / "postgresql")
    stage_project(package / "projecta")
    _verify_app_local_vc_runtime(package, receipt)
    trust_dir, public_key_fingerprint = _write_update_trust_module(release_eligible=args.release)
    if args.release and public_key_fingerprint != signing["publicKeyFingerprint"]:
        raise SystemExit("the frozen launcher trust anchor does not match the owner Ed25519 release key.")
    _freeze_launcher(package, trust_dir)
    authenticode_signing = _sign_authenticode_images(package, signing) if signing is not None else None
    native_dependencies = _write_native_dependency_manifest(package)
    write_notices(
        package,
        receipt,
        release_eligible=args.release,
        unsigned_pre_release_test=args.unsigned_pre_release_test,
        installer_tool_notice=args.installer_tool_notice,
    )
    manifest = write_manifest(
        package,
        public_key_fingerprint,
        release_eligible=args.release,
        unsigned_pre_release_test=args.unsigned_pre_release_test,
        authenticode_signing=authenticode_signing,
    )
    if signing is not None:
        signature_fingerprint = _write_ed25519_manifest_signature(
            package,
            signing["ed25519PrivateKey"],
        )
        if signature_fingerprint != public_key_fingerprint:
            raise SystemExit("the detached package signature does not match the compiled owner trust anchor.")
    verify_assembled(
        package,
        release_eligible=args.release,
        unsigned_pre_release_test=args.unsigned_pre_release_test,
    )
    archive = write_archive(package, archive_path)
    build_receipt = {
        "projectaVersion": APP_VERSION,
        "dataContractVersion": DATA_CONTRACT_VERSION,
        "releaseEligible": args.release,
        "distributionChannel": manifest["distributionChannel"],
        "sourceRevision": manifest["sourceRevision"],
        "unsignedPreReleaseException": (
            UNSIGNED_PRE_RELEASE_EXCEPTION if args.unsigned_pre_release_test else None
        ),
        "runtimeVersions": dict(RUNTIME_VERSIONS),
        "inputs": receipt,
        "package": str(package),
        "manifest": manifest,
        "nativeDependencies": {
            "imageCount": len(native_dependencies["images"]),
            "bundledModuleCount": len(native_dependencies["bundledModules"]),
            "unresolvedDependencies": native_dependencies["unresolvedDependencies"],
            "unverifiedDynamicStringCandidateCount": len(
                native_dependencies["unverifiedDynamicStringCandidates"]
            ),
        },
        "archive": archive,
        "signing": {
            "algorithm": "Ed25519",
            "publicKeyFingerprint": public_key_fingerprint,
            "signatureCreated": args.release,
            "authenticode": authenticode_signing,
            "reason": (
                "Owner Authenticode and Ed25519 signing completed and verified."
                if args.release
                else (
                    "Owner-authorized 0.7.0 unsigned test pre-release exception; neither Authenticode nor manifest signature is present."
                    if args.unsigned_pre_release_test
                    else "No owner release signature was produced; this host-validation archive is not distributable."
                )
            ),
        },
    }
    receipt_path = (
        ROOT / "build" / "native-package-build.json"
        if output_is_default
        else package.with_name(f"{package.name}-build.json")
    )
    receipt_path.write_text(json.dumps(build_receipt, indent=2) + "\n", encoding="utf-8")
    if args.release:
        print(f"assembled owner-signed release package {package} ({APP_VERSION})")
        print(f"archive {archive_path} sha256={archive['sha256']} size={archive['size']}")
        print(f"releaseEligible=true; Authenticode PE images={authenticode_signing['verifiedImageCount']}")
    elif args.unsigned_pre_release_test:
        print(f"assembled owner-authorized unsigned pre-release package {package} ({APP_VERSION})")
        print(f"archive {archive_path} sha256={archive['sha256']} size={archive['size']}")
        print("releaseEligible=false; unsigned pre-release exception is limited to 0.7.0.")
    else:
        print(f"assembled host-validation-only unsigned package {package} ({APP_VERSION})")
        print(f"archive {archive_path} sha256={archive['sha256']} size={archive['size']}")
        print(f"releaseEligible=false; owner signature absent; PE images={len(native_dependencies['images'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
