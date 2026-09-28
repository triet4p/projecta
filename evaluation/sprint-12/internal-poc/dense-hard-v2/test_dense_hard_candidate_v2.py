"""Candidate-side regression checks; source-only and provider-free."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_dense_hard_candidate_v2 import validate


HERE = Path(__file__).resolve().parent


class DenseHardCandidateV2Tests(unittest.TestCase):
    def test_strict_source_only_contract(self) -> None:
        self.assertEqual(validate(), [])

    def test_exact_case_and_artifact_counts(self) -> None:
        candidate = json.loads((HERE / "dense-hard-candidate.v2.json").read_text(encoding="utf-8"))
        self.assertEqual(len(candidate["responses"]), 28)
        self.assertEqual(candidate["agentCandidateCalls"], 28)
        self.assertEqual(candidate["providerCalls"], 0)
        self.assertFalse(candidate["goldIncluded"])
        self.assertFalse(candidate["priorReviewsIncluded"])
        self.assertFalse(candidate["scoring"])
        self.assertFalse(candidate["review"])


if __name__ == "__main__":
    unittest.main()
