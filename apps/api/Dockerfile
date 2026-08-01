FROM ghcr.io/astral-sh/uv:0.11.11 AS uv

FROM python:3.12-slim AS builder
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_PROGRESS=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev
COPY src ./src
RUN uv sync --locked --no-dev

FROM builder AS development
RUN uv sync --locked --all-groups
COPY tests ./tests
CMD ["uv", "run", "uvicorn", "projecta_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM development AS test
CMD ["uv", "run", "pytest", "-q"]

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN groupadd --system projecta && useradd --system --gid projecta --home-dir /app projecta
COPY --from=builder --chown=projecta:projecta /app/.venv /app/.venv
COPY --from=builder --chown=projecta:projecta /app/src /app/src
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1
USER projecta
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=12 CMD python -c "from urllib.request import urlopen; assert urlopen('http://127.0.0.1:8000/health/live').status == 200"
CMD ["uvicorn", "projecta_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
