# Python Build Baseline — Sprint 4

**Status:** APPROVED_FOR_S4-09
**Task:** S4-08

## Decision

Use `uv` with Python 3.12, `pyproject.toml`, and committed `uv.lock` for the
FastAPI application. S4-09 must create the first project and lock; this task
does not scaffold `apps/api` or select application dependency versions.

## Comparison

| Criterion | uv | Poetry | Selected rationale |
|---|---|---|
| Lock reproducibility | `uv.lock` supports a universal, exact resolved environment and locked sync. | `poetry.lock` provides reproducible resolves with Poetry-managed installation. | Both satisfy the requirement; uv has one fast resolver/sync workflow for local and container use. |
| Python toolchain | Can install and select the pinned Python runtime. | Relies on an existing interpreter or separate installer. | The repository’s Jena image already uses UV-managed Python 3.12. |
| Container workflow | A pinned `ghcr.io/astral-sh/uv` stage can produce dev, test, and runtime targets from the same lock. | Requires installing and pinning Poetry in each relevant build stage. | uv reduces one tool-install layer and matches the existing image practice. |
| Test/lint integration | Runs pytest, Ruff, and pyright from the locked environment with `uv run`. | Runs the same tools through `poetry run`. | Both are adequate; no separate Poetry convention exists in the repository. |
| Maintenance | One binary manages Python, resolution, sync, and command execution. | Mature project manager with plugins and a familiar workflow. | uv’s smaller setup is preferable for the first Python vertical slice. |

## Required S4-09 Layout and Commands

`apps/api/` must contain `pyproject.toml`, `uv.lock`, source package, and tests.
It must declare Python `>=3.12,<3.13` until a new decision changes the runtime.
CI and container targets must fail on a stale lock and install from the committed
lock only.

```text
uv sync --locked --all-groups
uv run pytest
uv run ruff check .
uv run pyright
```

The FastAPI image uses a pinned UV builder image, a non-root runtime user, and
the same lock in development, test, and runtime stages. The pinned UV image tag
or digest and dependency versions are S4-09/S4-10 implementation choices.

## Boundaries

This choice does not authorize a host Python installation, unpinned dependency
resolution in CI, a second requirements file, or Poetry files alongside
`uv.lock`. `uv` must be invoked as `uv run` in the existing Fuseki/Jena image
because the managed interpreter is not a system `python3` binary.
