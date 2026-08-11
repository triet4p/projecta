from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "architecture" / "connector-evidence-storage.md"


class Sprint10EvidenceContractTests(unittest.TestCase):
    def test_contract_covers_required_evidence_boundaries(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        required = (
            "# Connector Evidence Storage Contract",
            "## Port",
            "## Evidence object and metadata",
            "## Immutable/content-addressed write",
            "## Allowlist and limits",
            "## Bounded reads",
            "## Project isolation",
            "## Retention and safe deletion",
            "## Error contract",
            "## Restart, backup, and restore",
            "EVIDENCE_DIGEST_MISMATCH",
            "EVIDENCE_RETENTION_BLOCKED",
            "content-addressed",
        )

        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_contract_forbids_arbitrary_storage_and_raw_public_payloads(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        self.assertIn("There is no `list_all`, arbitrary-path read", text)
        self.assertIn("The Application API and browser receive only safe metadata", text)
        self.assertIn("Raw evidence is not copied into RDF or operational rows", text)
        self.assertIn("An interrupted write leaves no visible complete object", text)


if __name__ == "__main__":
    unittest.main()
