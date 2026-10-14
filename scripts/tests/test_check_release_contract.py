from pathlib import Path
from unittest import TestCase

from scripts.check_release_contract import (
    ReleaseContractError,
    declared_versions,
    desktop_lock_pins,
    release_notes,
    validate_desktop_locks,
    validate_release,
    version_from_tag,
)

ROOT = Path(__file__).resolve().parents[2]


class ReleaseContractTest(TestCase):
    def test_accepts_exact_semver_tag(self) -> None:
        self.assertEqual(version_from_tag("v0.4.0"), "0.4.0")

    def test_rejects_noncanonical_tags(self) -> None:
        for tag in ("0.4.0", "v0.4", "v01.4.0", "v0.4.0-rc1", "release-v0.4.0"):
            with self.subTest(tag=tag), self.assertRaises(ReleaseContractError):
                version_from_tag(tag)

    def test_extracts_only_requested_release_notes(self) -> None:
        changelog = """## [Unreleased]\n\n## [0.4.0] - 2026-08-10\n\n### Added\n\n- Current.\n\n## [0.3.0] - 2026-08-01\n\n### Added\n\n- Previous.\n"""
        notes = release_notes(changelog, "0.4.0")
        self.assertIn("Current", notes)
        self.assertNotIn("Previous", notes)

    def test_unsigned_release_keeps_release_contract_closed(self) -> None:
        self.assertEqual(set(declared_versions(ROOT).values()), {"0.7.1"})
        version, notes = validate_release(ROOT, "v0.7.1")
        self.assertEqual(version, "0.7.1")
        self.assertIn("### ", notes)

    def test_desktop_versions_join_the_closed_release_contract(self) -> None:
        versions = declared_versions(ROOT)
        self.assertEqual(
            {
                versions["desktop Cargo.toml"],
                versions["desktop package.json"],
                versions["desktop package-lock root"],
                versions["tauri.conf.json"],
            },
            {"0.7.1"},
        )
        self.assertEqual(set(versions.values()), {"0.7.1"})

    def test_desktop_lock_pins_match_the_reviewed_tauri_inputs(self) -> None:
        pins = validate_desktop_locks(ROOT)
        self.assertEqual(pins["cargo manifest tauri"], "=2.12.3")
        self.assertEqual(pins["cargo lock tauri"], "2.12.3")
        self.assertEqual(pins["npm lock node_modules/@tauri-apps/api"], "2.12.3")
        self.assertEqual(desktop_lock_pins(ROOT), pins)
