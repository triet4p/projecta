from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "architecture" / "connector-operational-storage.md"


class Sprint10OperationalStorageContractTests(unittest.TestCase):
    def test_contract_covers_required_operational_boundaries(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        required = (
            "# Connector Operational Storage Contract",
            "### `connector_installations`",
            "### `connector_event_inbox`",
            "### `connector_sync_runs`",
            "### `connector_sync_attempts`",
            "### `connector_cursors`",
            "### `connector_idempotency_keys`",
            "### `connector_dead_letters`",
            "### `connector_audit_events`",
            "## Transaction semantics",
            "## Retry and replay semantics",
            "## Retention and deletion",
            "## Migration contract",
            "## Backup, restore, and rollback",
            "## G1 decisions required",
        )

        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_contract_forbids_raw_payload_and_cursor_advance_on_failure(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        self.assertIn("raw credentials, provider payloads, filesystem paths", text)
        self.assertIn("It remains unchanged on validation, conflict, storage", text)
        self.assertIn("PostgreSQL never marks success or advances the cursor before Core success", text)
        self.assertIn("Connector operational rows never become RDF facts", text)


if __name__ == "__main__":
    unittest.main()
