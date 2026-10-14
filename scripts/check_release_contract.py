#!/usr/bin/env python3
"""Validate a Projecta SemVer tag and render its changelog release notes."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

TAG_PATTERN = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
RELEASE_HEADING = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$", re.MULTILINE)


class ReleaseContractError(ValueError):
    """The tag, manifests, or changelog do not form one release contract."""


def version_from_tag(tag: str) -> str:
    """Return the SemVer payload from an exact vA.B.C tag."""
    match = TAG_PATTERN.fullmatch(tag)
    if match is None:
        raise ReleaseContractError(f"release tag must match vA.B.C exactly: {tag}")
    return ".".join(match.groups())


def release_notes(changelog: str, version: str) -> str:
    """Return only the requested released changelog section."""
    matches = list(RELEASE_HEADING.finditer(changelog))
    selected = next((match for match in matches if match.group("version") == version), None)
    if selected is None:
        raise ReleaseContractError(f"CHANGELOG.md has no dated [{version}] release")
    following = next((match for match in matches if match.start() > selected.start()), None)
    end = following.start() if following is not None else len(changelog)
    notes = changelog[selected.end() : end].strip()
    if not notes or "### " not in notes:
        raise ReleaseContractError(f"CHANGELOG.md [{version}] release notes are empty")
    return notes + "\n"


def _desktop_cargo_version(root: Path) -> str:
    """Read the Tauri host crate version from its native Cargo manifest."""
    cargo = tomllib.loads((root / "apps/desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    try:
        version = cargo["package"]["version"]
    except KeyError as error:
        raise ReleaseContractError("Tauri Cargo.toml has no package version") from error
    return str(version)


def _desktop_web_version(root: Path) -> tuple[str, str]:
    """Read the desktop npm package version and its lockfile root version."""
    desktop_project = json.loads((root / "apps/desktop/package.json").read_text(encoding="utf-8"))
    desktop_lock = json.loads((root / "apps/desktop/package-lock.json").read_text(encoding="utf-8"))
    try:
        root_locked = desktop_lock["packages"][""]["version"]
    except KeyError as error:
        raise ReleaseContractError("desktop package-lock.json has no root package version") from error
    return str(desktop_project["version"]), str(root_locked)


def _tauri_conf_version(root: Path) -> str:
    """Read the Tauri application version from its native window config."""
    conf = json.loads((root / "apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    if "version" not in conf:
        raise ReleaseContractError("Tauri tauri.conf.json has no version")
    return str(conf["version"])


def desktop_lock_pins(root: Path) -> dict[str, str]:
    """Read the pinned Tauri/Rust/JS inputs that the desktop host builds from."""
    cargo = tomllib.loads((root / "apps/desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    cargo_lock = tomllib.loads((root / "apps/desktop/src-tauri/Cargo.lock").read_text(encoding="utf-8"))
    locked = {package["name"]: str(package["version"]) for package in cargo_lock["package"]}
    desktop_lock = json.loads((root / "apps/desktop/package-lock.json").read_text(encoding="utf-8"))
    node_packages = desktop_lock.get("packages", {})
    pins: dict[str, str] = {}
    try:
        build_deps = cargo["build-dependencies"]
        dependencies = cargo["dependencies"]
        for name in ("tauri-build",):
            pins[f"cargo manifest {name}"] = str(build_deps[name]["version"])
        for name in ("tauri", "serde", "serde_json", "url"):
            pins[f"cargo manifest {name}"] = str(dependencies[name]["version"])
    except KeyError as error:
        raise ReleaseContractError(f"Tauri Cargo.toml omits a pinned desktop dependency: {error}") from error
    for name in ("projecta-desktop", "tauri", "tauri-build", "serde", "serde_json", "url"):
        if name not in locked:
            raise ReleaseContractError(f"Tauri Cargo.lock omits a pinned package: {name}")
        pins[f"cargo lock {name}"] = locked[name]
    for path in ("node_modules/@tauri-apps/api", "node_modules/@tauri-apps/cli"):
        try:
            pins[f"npm lock {path}"] = str(node_packages[path]["version"])
        except KeyError as error:
            raise ReleaseContractError(f"desktop package-lock.json omits {path}") from error
    return pins


def validate_desktop_locks(root: Path) -> dict[str, str]:
    """Refuse a Tauri host whose manifests and lockfiles disagree with each other.

    This binds the new binary inputs to the release trust policy without
    inventing signatures: every desktop version carrier must agree, and every
    pinned manifest entry must resolve to the exact locked version.
    """
    versions = declared_versions(root)
    release_version = versions["VERSION"]
    cargo_version = _desktop_cargo_version(root)
    desktop_version, desktop_root_lock = _desktop_web_version(root)
    tauri_conf_version = _tauri_conf_version(root)
    mismatches = {
        name: value
        for name, value in {
            "desktop Cargo.toml": cargo_version,
            "desktop package.json": desktop_version,
            "desktop package-lock root": desktop_root_lock,
            "tauri.conf.json": tauri_conf_version,
        }.items()
        if value != release_version
    }
    if mismatches:
        detail = ", ".join(f"{name}={value}" for name, value in sorted(mismatches.items()))
        raise ReleaseContractError(f"desktop release {release_version} has mismatched Tauri versions: {detail}")
    pins = desktop_lock_pins(root)
    cargo_lock = tomllib.loads((root / "apps/desktop/src-tauri/Cargo.lock").read_text(encoding="utf-8"))
    locked = {package["name"]: str(package["version"]) for package in cargo_lock["package"]}
    expected_manifest: dict[str, str] = {
        "cargo manifest tauri-build": "=2.7.2",
        "cargo manifest tauri": "=2.12.3",
        "cargo manifest serde": "=1.0.228",
        "cargo manifest serde_json": "=1.0.149",
        "cargo manifest url": "=2.5.8",
    }
    drift = {
        name: pins[name] for name in expected_manifest if pins.get(name) != expected_manifest[name]
    }
    for name, pinned in expected_manifest.items():
        locked_name = name.replace("cargo manifest ", "cargo lock ")
        if locked.get(locked_name.replace("cargo lock ", "")) != pinned.lstrip("="):
            drift[locked_name] = locked.get(locked_name.replace("cargo lock ", ""), "<absent>")
    desktop_lock = json.loads((root / "apps/desktop/package-lock.json").read_text(encoding="utf-8"))
    node_packages = desktop_lock.get("packages", {})
    if str(node_packages.get("node_modules/@tauri-apps/api", {}).get("version")) != "2.12.3":
        drift["npm lock node_modules/@tauri-apps/api"] = str(
            node_packages.get("node_modules/@tauri-apps/api", {}).get("version")
        )
    if str(node_packages.get("node_modules/@tauri-apps/cli", {}).get("version")) != "2.12.2":
        drift["npm lock node_modules/@tauri-apps/cli"] = str(
            node_packages.get("node_modules/@tauri-apps/cli", {}).get("version")
        )
    if drift:
        detail = ", ".join(f"{name}={value}" for name, value in sorted(drift.items()))
        raise ReleaseContractError(f"desktop lock pins drifted from the reviewed Tauri inputs: {detail}")
    return pins


def declared_versions(root: Path) -> dict[str, str]:
    """Read every product component version from its native manifest."""
    api_project = tomllib.loads((root / "apps/api/pyproject.toml").read_text(encoding="utf-8"))
    api_lock = tomllib.loads((root / "apps/api/uv.lock").read_text(encoding="utf-8"))
    api_lock_version = next(
        package["version"] for package in api_lock["package"] if package["name"] == "projecta-api"
    )
    web_project = json.loads((root / "apps/web/package.json").read_text(encoding="utf-8"))
    web_lock = json.loads((root / "apps/web/package-lock.json").read_text(encoding="utf-8"))
    pom = ET.parse(root / "services/semantic-core/pom.xml").getroot()
    pom_namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
    semantic_version = pom.findtext("m:version", namespaces=pom_namespace)
    if semantic_version is None:
        raise ReleaseContractError("Semantic Core pom.xml has no project version")
    api_main = (root / "apps/api/src/projecta_api/main.py").read_text(encoding="utf-8")
    api_runtime_match = re.search(
        r'FastAPI\(title="Projecta Application API", version="([^"]+)"[^)]*\)', api_main
    )
    if api_runtime_match is None:
        raise ReleaseContractError("Application API main.py has no runtime version")
    desktop_cargo_version = _desktop_cargo_version(root)
    desktop_version, desktop_root_lock = _desktop_web_version(root)
    tauri_conf_version = _tauri_conf_version(root)
    return {
        "VERSION": (root / "VERSION").read_text(encoding="utf-8").strip(),
        "api pyproject": str(api_project["project"]["version"]),
        "api lock": str(api_lock_version),
        "api runtime": api_runtime_match.group(1),
        "web package": str(web_project["version"]),
        "web lock": str(web_lock["version"]),
        "web root lock": str(web_lock["packages"][""]["version"]),
        "semantic core": semantic_version,
        "desktop Cargo.toml": desktop_cargo_version,
        "desktop package.json": desktop_version,
        "desktop package-lock root": desktop_root_lock,
        "tauri.conf.json": tauri_conf_version,
    }


def validate_release(root: Path, tag: str) -> tuple[str, str]:
    """Validate the complete release contract and return version plus notes."""
    version = version_from_tag(tag)
    mismatches = {
        name: value for name, value in declared_versions(root).items() if value != version
    }
    if mismatches:
        detail = ", ".join(f"{name}={value}" for name, value in sorted(mismatches.items()))
        raise ReleaseContractError(f"release {version} does not match component versions: {detail}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if "## [Unreleased]" not in changelog:
        raise ReleaseContractError("CHANGELOG.md must retain an Unreleased section")
    return version, release_notes(changelog, version)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--notes-output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        version, notes = validate_release(root, args.tag)
        validate_desktop_locks(root)
    except (OSError, KeyError, StopIteration, ReleaseContractError, tomllib.TOMLDecodeError) as error:
        print(f"Release contract failed: {error}", file=sys.stderr)
        return 1
    if args.notes_output is not None:
        args.notes_output.write_text(notes, encoding="utf-8")
    print(f"Release contract verified for v{version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
