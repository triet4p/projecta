import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Sprint10ReleaseWorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    def test_publish_requires_all_sprint10_jobs(self) -> None:
        for job in (
            "sprint10-validation",
            "sprint10-acceptance",
            "sprint10-recovery",
            "sprint10-frontend-format",
            "sprint10-connector-security",
        ):
            self.assertIn(job, self.source)
        publish = self.source.split("\n  publish:", 1)[1]
        self.assertIn("needs:", publish)
        for job in (
            "sprint10-validation",
            "sprint10-acceptance",
            "sprint10-recovery",
            "sprint10-frontend-format",
            "sprint10-connector-security",
        ):
            self.assertIn(job, publish)

    def test_sprint10_release_jobs_have_no_bypass(self) -> None:
        sprint10 = self.source.split("\n  sprint10-validation:", 1)[1].split("\n  publish:", 1)[0]
        self.assertNotIn("continue-on-error", sprint10)
        self.assertNotIn("if: always()", sprint10)
        self.assertIn("run_sprint10_validation.ps1", sprint10)
        self.assertIn("run_sprint10_acceptance.ps1", sprint10)
        self.assertIn("run_sprint10_recovery.ps1", sprint10)


if __name__ == "__main__":
    unittest.main()
