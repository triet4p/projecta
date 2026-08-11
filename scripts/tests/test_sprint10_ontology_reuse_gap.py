from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "docs" / "ontology" / "sprint-10-connector-reuse-gap.md"


class Sprint10OntologyReuseGapTests(unittest.TestCase):
    def test_audit_records_no_change_outcome_and_review_gate(self) -> None:
        text = PACKET.read_text(encoding="utf-8")

        required = (
            "`APPROVED_FOR_RELEASE`",
            "`NO_ONTOLOGY_CHANGE_REQUIRED`",
            "## Justification",
            "## Competency questions",
            "## Semantic commitment gate",
            "## Alternatives considered",
            "## Artifact diff",
            "## Validation evidence",
            "## Compatibility and risk",
            "## Unresolved questions",
            "## Human actions requested",
        )

        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_audit_keeps_operational_connector_state_out_of_ontology(self) -> None:
        text = PACKET.read_text(encoding="utf-8")

        self.assertIn("No new Projecta class, object property, datatype property", text)
        self.assertIn("sync run, single attempt, cursor, idempotency key", text)
        self.assertIn("They belong in PostgreSQL, the evidence store", text)
        self.assertIn("No production ontology artifact is changed", text)
        self.assertIn("Human approval of the reuse outcome was recorded at G1", text)
        self.assertIn("does not pre-approve a future ontology vocabulary change", text)


if __name__ == "__main__":
    unittest.main()
