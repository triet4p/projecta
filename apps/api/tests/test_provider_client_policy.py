"""Static regression for provider SDK behavior hidden below gateway policy."""

import ast
from pathlib import Path

import pytest

PRODUCTION_CLIENT_FILES = (
    "src/projecta_api/llm/openai_responses.py",
    "src/projecta_api/configuration/connection.py",
    "src/projecta_api/retrieval/live.py",
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("relative_path", PRODUCTION_CLIENT_FILES)
def test_every_openai_client_explicitly_disables_sdk_retries(relative_path: str) -> None:
    source_path = PACKAGE_ROOT / relative_path
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AsyncOpenAI"
    ]

    assert constructors, f"no AsyncOpenAI constructor found in {relative_path}"
    for constructor in constructors:
        retry_keyword = next(
            (keyword for keyword in constructor.keywords if keyword.arg == "max_retries"),
            None,
        )
        assert retry_keyword is not None, f"{relative_path} relies on implicit SDK retry"
        assert isinstance(retry_keyword.value, ast.Constant)
        assert retry_keyword.value.value == 0
