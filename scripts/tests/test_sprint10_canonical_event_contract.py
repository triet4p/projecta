from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "architecture" / "canonical-event-contract.md"


class Sprint10CanonicalEventContractTests(unittest.TestCase):
    def test_contract_contains_required_boundary_sections(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        required = (
            "# Canonical Event Contract",
            "## Canonical envelope",
            "## Stable event identity and idempotency",
            "## Canonical serialization and hashing",
            "## Bounds",
            "## Validation order",
            "## Typed validation problems",
            "## Semantic boundary",
            "EVENT_BODY_CONFLICT",
            "projectScope",
            "installationScope",
            "contentHash",
            "canonicalBodyHash",
        )

        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_contract_forbids_domain_assertions_in_the_event_envelope(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        self.assertIn("does not contain a domain assertion", text)
        self.assertIn("no Requirement, Task, relation, assertion status", text)
        self.assertIn("Operational event state remains outside RDF", text)


if __name__ == "__main__":
    unittest.main()
