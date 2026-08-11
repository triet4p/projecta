from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "architecture" / "connector-contract.md"


class Sprint10ConnectorContractTests(unittest.TestCase):
    def test_contract_covers_required_adapter_operations(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        required = (
            "# Connector Adapter Contract",
            "## Adapter descriptor and finite capabilities",
            "## Installation validation",
            "## Bounded pull/import",
            "## Resource fetch",
            "## Identity hint",
            "## Cursor contract",
            "## Cancellation and deadline behavior",
            "## Typed adapter errors",
            "## Registry and dependency direction",
            "pull_events",
            "fetch_resource",
            "resolve_identity_hint",
        )

        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_contract_preserves_no_retry_and_no_semantic_mutation_boundaries(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        self.assertIn("never add SDK, HTTP, proxy, scheduler, worker, or recursive retries", text)
        self.assertIn("does not decide Projecta authorization, create domain facts", text)
        self.assertIn("Semantic Core depends on canonical source/provenance contracts", text)
        self.assertIn("never commits its own cursor", text)


if __name__ == "__main__":
    unittest.main()
