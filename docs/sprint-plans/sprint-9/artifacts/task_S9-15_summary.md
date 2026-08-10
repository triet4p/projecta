# Task Summary: Cut the Projecta 0.4.0 version

**Sprint:** Sprint 9 — Provider Runtime Truthfulness
**Task:** S9-15

## Summary of Work

Established `VERSION` as the repository release source, aligned the API, web,
lockfile, runtime metadata, and Semantic Core Maven version to `0.4.0`, and
froze a dated user-facing `CHANGELOG.md` section while retaining a fresh
Unreleased section.

## Files Modified

* `VERSION`
* `CHANGELOG.md`
* `apps/api/pyproject.toml`
* `apps/api/uv.lock`
* `apps/api/src/projecta_api/main.py`
* `apps/web/package.json`
* `apps/web/package-lock.json`
* `services/semantic-core/pom.xml`

## Testing

* The release contract resolves every component as `0.4.0` for tag `v0.4.0`.
* API: `128 passed, 3 skipped`; Pyright and Ruff clean.
* Web: 15 tests; typecheck, lint, build, Nginx, drift, and audit gates pass.
* Semantic Core: 49 tests pass; ontology validation is `140/140`.

## Additional Notes

No ontology vocabulary or IRI changed as part of the release cut.
