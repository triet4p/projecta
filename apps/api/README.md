# Projecta Application API

FastAPI application boundary for the Manual Quick Note slice. It calls the
Semantic Core through finite, typed operations and never accesses Fuseki.

Run checks from this directory:

```text
uv sync --locked --all-groups
uv run pytest
uv run ruff check .
uv run pyright
```
