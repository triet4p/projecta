"""Make the repository-root pytest invocation use the canonical script paths."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "scripts", ROOT / "apps" / "api" / "src"):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
