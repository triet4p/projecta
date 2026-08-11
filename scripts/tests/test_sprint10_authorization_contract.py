from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "architecture" / "connector-authorization.md"


class Sprint10AuthorizationContractTests(unittest.TestCase):
    def test_contract_covers_server_owned_authorization_boundaries(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        required = (
            "# Connector Authorization Contract",
            "## Server-owned principal",
            "## Local experience adapter",
            "## Finite connector operations",
            "## Decision matrix",
            "## Project and installation scope",
            "## Opaque handles and stale revisions",
            "## Safe public mapping",
            "## Correlation and audit",
            "## Secret boundary",
            "PROJECT_CONTEXT_REQUIRED",
            "PROJECT_FORBIDDEN",
            "RESOURCE_NOT_FOUND",
            "sync.retry",
        )

        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_contract_rejects_browser_and_local_mode_as_authority(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        self.assertIn("The browser, connector adapter, fixture, event payload", text)
        self.assertIn("It is disabled or rejected in `production` mode", text)
        self.assertIn("Raw credentials, secret references, raw payload", text)
        self.assertIn("Retry additionally requires the expected failed-run revision", text)


if __name__ == "__main__":
    unittest.main()
