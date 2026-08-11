import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Sprint10AcceptanceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = (ROOT / "scripts" / "run_sprint10_acceptance.ps1").read_text(encoding="utf-8")

    def test_runner_executes_all_seven_journeys_and_restarts_stateful_services(self) -> None:
        for journey in range(1, 8):
            self.assertIn(f"Journey {journey}", self.source)
        self.assertIn("up -d --build", self.source)
        self.assertIn("restart api web connector-postgres", self.source)
        self.assertIn("down --volumes --remove-orphans", self.source)

    def test_runner_scans_correlated_logs_and_forbidden_values(self) -> None:
        self.assertIn("requestId.*operationId", self.source)
        self.assertIn("secretReference", self.source)
        self.assertIn("https://w3id.org/projecta/", self.source)


if __name__ == "__main__":
    unittest.main()
