import unittest
from pathlib import Path

from scripts.check_sprint10_repository_contract import validate


ROOT = Path(__file__).resolve().parents[2]


class Sprint10RepositoryContractTests(unittest.TestCase):
    def test_repository_contract_is_clean(self) -> None:
        self.assertEqual(validate(ROOT), [])


if __name__ == "__main__":
    unittest.main()
