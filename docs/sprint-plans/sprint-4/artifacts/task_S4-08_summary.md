# Task Summary: S4-08 — Select the Python build baseline

**Sprint:** Sprint 4
**Task:** S4-08

## Summary of Work

Selected uv with Python 3.12, `pyproject.toml`, and `uv.lock` after comparing
lock reproducibility, container workflow, test/lint integration, and
maintenance against Poetry.

## Files Modified

- `docs/architecture/python-build-baseline.md` — comparison and required commands.
- `.agents/memory/decisions.md` — append-only architectural decision.

## Testing

- **Test File:** Not applicable; no Python project exists before S4-09.
- **Status:** Decision aligns with the existing UV-managed container lesson;
  released ontology regression passed (73/73).
- **Execution Command:** `docker compose run --build --rm ontology-test`

## Additional Notes

S4-09 must create the lock and S4-10 must pin its container build stage; this
task intentionally does neither.
