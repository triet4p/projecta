import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Sprint10RecoveryRunnerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = (ROOT / "scripts" / "run_sprint10_recovery.ps1").read_text(encoding="utf-8")

    def test_runner_covers_backup_teardown_restore_replay_and_cleanup(self) -> None:
        for marker in (
            "connector_backup.py backup",
            "Teardown source stack",
            "connector_recovery_drill.py",
            "connector_recovery_fixture.py verify",
            "docker logs",
            "Remove-Item -LiteralPath $tempRoot -Recurse -Force",
        ):
            self.assertIn(marker, self.source)

    def test_restore_requires_isolated_confirmation(self) -> None:
        self.assertIn("--confirm-quiesced", self.source)
        self.assertIn("--confirm-isolated", self.source)
        self.assertIn("connector-backup.v1", self.source)


if __name__ == "__main__":
    unittest.main()
