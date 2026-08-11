from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "docs" / "architecture" / "connector-threat-model.md"


class Sprint10ThreatModelTests(unittest.TestCase):
    def test_threat_model_covers_required_ingestion_threats(self) -> None:
        text = MODEL.read_text(encoding="utf-8")

        required = (
            "# Connector Ingestion Threat Model",
            "Forged project/actor/trusted headers",
            "Cross-project event replay",
            "Confused deputy",
            "SSRF or arbitrary network access",
            "Path traversal/local file read",
            "Payload bomb/resource exhaustion",
            "Malicious JSON",
            "Secret leakage",
            "Cursor tampering or premature advance",
            "Duplicate delivery",
            "Partial commit",
            "Disabled-installation race",
            "## Security invariants",
            "## Required abuse/failure tests",
        )

        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_threat_model_preserves_semantic_and_redaction_boundaries(self) -> None:
        text = MODEL.read_text(encoding="utf-8")

        self.assertIn("No imported source becomes an assertion", text)
        self.assertIn("No raw secret/payload/internal storage/semantic identifier", text)
        self.assertIn("The JSON/Mock adapter has no network capability", text)
        self.assertIn("No cursor advances without", text)


if __name__ == "__main__":
    unittest.main()
