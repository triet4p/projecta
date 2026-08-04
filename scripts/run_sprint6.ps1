$ErrorActionPreference = "Stop"
docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml run --build --rm ontology-test
uv run --project apps/api python evaluation/sprint-6/run_offline.py
uv run --project apps/api ruff check apps/api/src apps/api/tests evaluation/sprint-6
uv run --project apps/api pyright apps/api/src/projecta_api/retrieval apps/api/src/projecta_api/routes.py
uv run --project apps/api pytest -q apps/api/tests
Push-Location services/semantic-core
try { mvn --batch-mode test } finally { Pop-Location }
& .\scripts\run_system_tests.ps1
git diff --check
