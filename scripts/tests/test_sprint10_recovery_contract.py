import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from connector_backup import BACKUP_VERSION, _database_args


class Sprint10RecoveryContractTests(unittest.TestCase):
    def test_backup_version_and_database_password_boundary(self) -> None:
        args, env = _database_args(
            "postgresql+psycopg://connector:password@example:5432/projecta",
            "password",
        )
        self.assertEqual(BACKUP_VERSION, "connector-backup.v1")
        self.assertNotIn("password", " ".join(args))
        self.assertEqual(env["PGPASSWORD"], "password")

    def test_restore_requires_isolated_confirmation_and_no_production_default(self) -> None:
        source = (ROOT / "scripts" / "connector_backup.py").read_text(encoding="utf-8")
        self.assertIn("confirm-quiesced", source)
        self.assertIn("confirm-isolated", source)
        self.assertIn("isolated restore target is unsafe", source)
        self.assertNotIn("--database-password", source)


if __name__ == "__main__":
    unittest.main()
