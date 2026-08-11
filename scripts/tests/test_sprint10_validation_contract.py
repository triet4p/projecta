import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Sprint10ValidationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = (ROOT / "scripts" / "run_sprint10_validation.ps1").read_text(encoding="utf-8")

    def test_runner_contains_every_required_gate_and_cleanup(self) -> None:
        required = (
            "Release-contract unit tests",
            "API Ruff",
            "API Pyright",
            "API full tests",
            "Web dependency audit",
            "Web format",
            "Web API drift",
            "Deterministic browser tests",
            "Semantic Core verification",
            "Ontology validation",
            "Connector migration and integration",
            "Sprint 10 repository contract",
            "Secret leak gate",
            "Whitespace contract",
            "down --volumes --remove-orphans",
        )
        for marker in required:
            self.assertIn(marker, self.source)

    def test_runner_has_no_gate_skip_switch_and_rejects_dirty_checkout(self) -> None:
        self.assertIn("requires a clean checkout", self.source)
        self.assertIn("-AllowDirtyWorktree", self.source)
        self.assertNotRegex(self.source, r"\[switch\]\$Skip")
        self.assertIn("exit 1", self.source)

    def test_browser_artifacts_cannot_mutate_tracked_release_evidence(self) -> None:
        browser_source = (ROOT / "apps/web/tests/e2e/sprint8.spec.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("testInfo.outputPath(screenshotName)", browser_source)
        self.assertNotIn("docs/sprint-plans/sprint-8/evidence", browser_source)


if __name__ == "__main__":
    unittest.main()
