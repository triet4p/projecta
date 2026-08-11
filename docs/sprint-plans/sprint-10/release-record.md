# Sprint 10 Release Record

Status: `COMPLETE`

Release: `v0.5.1`

Published: 2026-08-11

## Immutable release target

- G3-approved commit: `d5ff40d7c64966e03ae266ceeb39d7092899d9fb`.
- Annotated tag: `v0.5.1`.
- Tag object: `7ad8517b41424344e4d00eef77a1cc8962dab622`.
- Remote peeled target: `d5ff40d7c64966e03ae266ceeb39d7092899d9fb`.
- Remote `main` at publication: `d5ff40d7c64966e03ae266ceeb39d7092899d9fb`.
- Historical failed tag `v0.5.0` remains unchanged: tag object
  `01638a4ec676d75610e03ac6dc6b6023f0a67fde`, peeled target
  `dd1fcccca18647238bf37731fde6c5a7e8fc7726`.

## Human gates

- G1 approved the connector architecture, security, storage, evidence, and
  ontology-reuse boundaries.
- G2 approved product, security, and semantic readiness.
- Recovery approval explicitly selected `v0.5.1` instead of moving or
  recreating `v0.5.0`.
- G3 explicitly approved
  `d5ff40d7c64966e03ae266ceeb39d7092899d9fb` as `v0.5.1`.

## Immutable local preflight

The exact G3 commit completed the mandatory local matrix without a tracked file
change afterward:

- Release-contract tests: 34 passed; `check_release_contract.py --tag v0.5.1`
  passed.
- API: Ruff passed, Pyright reported zero errors/warnings, and Pytest reported
  170 passed with five unchanged baseline skips.
- Web: dependency audit reported zero vulnerabilities; format, typecheck, lint,
  API drift, Nginx contract, and production build passed; Vitest reported 17/17
  and deterministic Playwright reported 6/6.
- Semantic Core: Maven verification reported 50/50 tests passed.
- Ontology: canonical Compose validation reported 140/140 checks passed.
- Connector PostgreSQL integration: 2/2 passed.
- Legacy Compose system path: API reported 165 passed, two unchanged baseline
  skips, and eight repository-only tests deselected; Semantic Core and ontology
  gates passed.
- Clean-Compose acceptance passed all seven journeys, including real-browser
  import/accessible operation, evidence lifecycle, replay, isolation, failure
  truthfulness, recovery contracts, restart, and post-restart browser checks.
- Isolated PostgreSQL/evidence backup, teardown, clean restore, and replay passed
  with one run row, unchanged cursor revision/checkpoint, and unchanged evidence
  digest.
- Final worktree and Docker cleanup checks were clean.

Preflight log SHA-256 digests:

- Validation: `ed09a5e174dd8dd9b16f98ebb9a079a0cb5ac2606f6ad796974081a53c789751`.
- System: `aa55f17549f857a5abbb66309de002e6552c23408bb47ab8659b97b2992b7f73`.
- Acceptance: `bd65d76f18dd3167cbcb933bb4ec23f8030c1ff89e7cba1a0847047b7e30c59b`.
- Recovery evidence: `ff8c8d5f1ce6d452dd4bf08c0623a34f8df233e07d3f6c8c8ccebdd7adb106eb`.

## Tag workflow and publication

- GitHub Actions run:
  `https://github.com/triet4p/projecta/actions/runs/31467464801`.
- Exact workflow head: tag `v0.5.1`, commit
  `d5ff40d7c64966e03ae266ceeb39d7092899d9fb`.
- Required release-contract, API, web, Semantic Core, repository-contract,
  system, Sprint 10 validation, acceptance, recovery, frontend-format,
  connector-security, and publish jobs completed successfully.
- The first API attempt timed out downloading the pinned OpenAI wheel from
  PyPI after three transport retries. The same locked dependency sync had
  already succeeded in the web job on the same SHA. The failed jobs were rerun
  once with no source or tag change; API and publish then passed.
- Public release:
  `https://github.com/triet4p/projecta/releases/tag/v0.5.1`.
- GitHub reports `Projecta 0.5.1`, published at `2026-08-11T07:11:53Z`, with
  `isDraft=false` and `isPrerelease=false`.
- Published notes contain only the dated `0.5.1` changelog content.

## Closure

Sprint 10 is complete. M7 remains in progress; production authentication,
tenant administration, server-side secret-manager integration, the first real
connector, outbound actions, and broader production hardening remain Sprint
11+ scope.

The non-blocking GitHub Actions warning that `astral-sh/setup-uv@v6` targets the
deprecated Node.js 20 action runtime remains maintenance follow-up; GitHub ran
the action under Node.js 24 and all required release gates passed.
