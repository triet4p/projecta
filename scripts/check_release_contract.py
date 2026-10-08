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
    return {
        "VERSION": (root / "VERSION").read_text(encoding="utf-8").strip(),
        "api pyproject": str(api_project["project"]["version"]),
        "api lock": str(api_lock_version),
        "api runtime": api_runtime_match.group(1),
        "web package": str(web_project["version"]),
        "web lock": str(web_lock["version"]),
        "web root lock": str(web_lock["packages"][""]["version"]),
        "semantic core": semantic_version,
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
    try:
        version, notes = validate_release(args.root.resolve(), args.tag)
    except (OSError, KeyError, StopIteration, ReleaseContractError, tomllib.TOMLDecodeError) as error:
        print(f"Release contract failed: {error}", file=sys.stderr)
        return 1
    if args.notes_output is not None:
        args.notes_output.write_text(notes, encoding="utf-8")
    print(f"Release contract verified for v{version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
