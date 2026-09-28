"""Source-only contract tests for the dense-hard v3 candidate."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v3"
CANDIDATE = PACKET / "dense-hard-candidate.v3.json"
BUILD = ROOT / "scripts/build_s12_dense_hard_v3_candidate.py"
VALIDATE = ROOT / "scripts/validate_s12_dense_hard_v3_candidate.py"


class DenseHardV3CandidateSourceOnlyTests(unittest.TestCase):
    def test_build_and_validate(self) -> None:
        built = subprocess.run([sys.executable, str(BUILD)], cwd=ROOT, check=True, capture_output=True, text=True)
        self.assertIn('"records": 30', built.stdout)
        validated = subprocess.run([sys.executable, str(VALIDATE)], cwd=ROOT, check=True, capture_output=True, text=True)
        self.assertIn('"records": 30', validated.stdout)

    def test_source_only_and_call_guard(self) -> None:
        candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
        self.assertTrue(candidate["sourceOnly"])
        self.assertEqual(candidate["agentCandidateCalls"], 30)
        self.assertEqual(candidate["providerCalls"], 0)
        self.assertFalse(candidate["goldUsed"])
        self.assertFalse(candidate["priorReviewUsed"])
        self.assertFalse(candidate["scoringPerformed"])

    def test_unicode_occurrence_anchors_are_exact(self) -> None:
        source = json.loads((PACKET / "dense-hard-source-payload.v3.json").read_text(encoding="utf-8"))
        candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
        raw_by_case = {record["caseId"]: record["rawText"] for record in source["records"]}
        candidate_case = {record["caseId"]: record for record in candidate["records"]}
        for case_id in ("dh3-013", "dh3-014", "dh3-015", "dh3-016", "dh3-023", "dh3-024"):
            raw = raw_by_case[case_id]
            for entity in candidate_case[case_id]["entities"]:
                occurrence = entity["occurrence"]
                self.assertEqual(raw[occurrence["startOffset"] : occurrence["endOffset"]], occurrence["text"])


if __name__ == "__main__":
    unittest.main()
