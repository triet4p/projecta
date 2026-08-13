from pathlib import Path
import re
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]


class Sprint11ReleaseWorkflowContractTests(TestCase):
    def setUp(self) -> None:
        self.source = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    def test_publish_requires_sprint11_gates(self) -> None:
        publish = self.source.split("\n  publish:", 1)[1]
        for job in ("sprint11-deterministic", "sprint11-acceptance", "sprint11-recovery"):
            self.assertIn(job, self.source)
            self.assertIn(job, publish)

    def test_sprint11_gates_are_deterministic_and_no_live_provider_job(self) -> None:
        for job in ("sprint11-deterministic", "sprint11-acceptance", "sprint11-recovery"):
            section = self.source.split(f"\n  {job}:", 1)[1]
            next_job = re.search(r"\n  [a-z0-9-]+:", section)
            if next_job is not None:
                section = section[: next_job.start()]
            self.assertNotIn("continue-on-error", section)
            self.assertNotIn("if: always()", section)
        self.assertIn("run_sprint11_validation.ps1 -SkipComposeConfig", self.source)
        self.assertIn("run_sprint11_clean_compose.ps1 -ConfigOnly", self.source)
        self.assertNotIn("run_sprint11_github_public_issues_acceptance.ps1", self.source)
        self.assertIn("quota waiver", self.source)


if __name__ == "__main__":
    import unittest

    unittest.main()
