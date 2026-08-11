"""Seeded connector leak gate for public DTOs, web source, and review artifacts."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Sprint10ConnectorLeakTests(unittest.TestCase):
    def test_public_connector_models_do_not_accept_secret_or_storage_references(self) -> None:
        public_api = (
            ROOT / "apps" / "api" / "src" / "projecta_api" / "connectors" / "public_api.py"
        ).read_text(encoding="utf-8")
        forbidden = ('alias="secretReference"', 'alias="contentRef"', 'alias="eventId"', 'alias="storagePath"', 'alias="graphIri"')
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, public_api)

    def test_browser_source_and_connector_artifacts_contain_no_seeded_secret_or_raw_fixture(self) -> None:
        roots = (
            ROOT / "apps" / "web" / "src",
            ROOT / "apps" / "web" / "tests" / "e2e" / "sprint10.spec.ts",
            ROOT / "docs" / "sprint-plans" / "sprint-10" / "artifacts",
        )
        forbidden = ("super-secret", "password=", "Authorization: Bearer", "private-store")
        paths = [roots[1]] if roots[1].is_file() else []
        for root in (roots[0], roots[2]):
            paths.extend(root.rglob("*.ts" if root == roots[0] else "*.md"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path, marker=marker):
                    self.assertNotIn(marker.lower(), text.lower())


if __name__ == "__main__":
    unittest.main()
