"""Repository-wide test guards for immutable Sprint 12 evaluation artifacts."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "scripts", ROOT / "apps" / "api" / "src"):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
IMMUTABLE = (
    "s12-f-12-stage-a-report.v6.json",
    "s12-f-12-stage-a-report.v9.json",
)
ABSENT = OPTIMIZATION / "s12-f-12-stage-a-report.v8.json"


def _snapshot() -> dict[str, str | None]:
    return {
        name: hashlib.sha256((OPTIMIZATION / name).read_bytes()).hexdigest()
        for name in IMMUTABLE
    } | {ABSENT.name: None if not ABSENT.exists() else "present"}


@pytest.fixture(scope="session", autouse=True)
def immutable_evaluation_artifact_guard():
    """Ensure the complete historical suite cannot mutate archived reports."""

    before = _snapshot()
    assert all((OPTIMIZATION / name).is_file() for name in IMMUTABLE)
    assert not ABSENT.exists()
    yield
    after = _snapshot()
    assert after == before, "historical immutable reports changed during the test session"


def test_mock_tests_do_not_delete_immutable_report_paths() -> None:
    """Keep destructive mock cleanup restricted to temporary/test-owned paths."""

    destructive_markers = (".unlink", "os.remove", "rmtree", "Remove-Item")
    immutable_markers = IMMUTABLE
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        if any(marker in source for marker in destructive_markers):
            assert not (
                any(marker in source for marker in immutable_markers)
                and any(marker in source for marker in destructive_markers)
            ), f"{path.name} combines immutable report references with destructive cleanup"
