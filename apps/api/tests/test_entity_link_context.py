"""Application contract tests for the bounded Semantic Core link-context read."""

import pytest

from projecta_api.context import TrustedRequestContext
from projecta_api.semantic_core import HttpSemanticCoreClient


@pytest.mark.asyncio
async def test_link_context_limit_is_bounded_before_downstream_call() -> None:
    client = HttpSemanticCoreClient("http://semantic-core")

    with pytest.raises(ValueError):
        await client.entity_link_context(TrustedRequestContext("project", "actor", "request"), 101)
