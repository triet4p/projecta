from pathlib import Path
from unittest import TestCase

from scripts.check_release_contract import (
    ReleaseContractError,
    declared_versions,
    release_notes,
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

    def test_repository_manifests_match_release(self) -> None:
        self.assertEqual(set(declared_versions(ROOT).values()), {"0.4.0"})
        version, notes = validate_release(ROOT, "v0.4.0")
        self.assertEqual(version, "0.4.0")
        self.assertIn("### Added", notes)
