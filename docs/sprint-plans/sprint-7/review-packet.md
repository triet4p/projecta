# Sprint 7 review packet — pending human approval

Status: `READY_FOR_HUMAN_REVIEW`
Scope: S7-36 through S7-46
Decision gate: S7-47 remains pending. This packet is evidence for review, not
product or security acceptance.

## Delivered boundary

The React/TypeScript SPA now covers the released extraction, typed capture,
Requirement-only review, knowledge/evidence, grounded Q&A, diagnostics, and
redacted LLM settings workflows. It is containerized as a static Nginx image
behind a same-origin `/v1` and `/health` proxy. The API keeps fixed experience
context server-side and resolves encrypted operational credentials at operation
time.

## Evidence matrix

| Area | Evidence | Status |
| --- | --- | --- |
| Accessibility | Skip link, main landmark focus, semantic nav/buttons, labeled fields, live state/error announcements, narrow CSS layout | Implemented; browser runner evidence pending |
| Web image/Compose | `apps/web/Dockerfile`, `nginx.conf`, `web` profile, API/web health checks, production immutable image override | Production web image build and merged config passed; local-image real-stack acceptance passed before and after API/web restart |
| Backend settings | `test_interactive_configuration.py`, runtime/environment adapter tests | Implemented and locally validated; first-run LLM bootstrap is optional, connection health persists, removal requires `confirm: true` |
| Frontend unit state | `form-state.test.ts`, `workflows.test.ts`, `client.test.ts` | Implemented and locally validated |
| API drift | generated client, snapshot forbidden-field check, backend public-path comparison, CI workflow | Implemented and locally validated |
| Browser E2E | `apps/web/tests/e2e/sprint7.spec.ts`, `playwright.config.ts`, deterministic route fixtures | Passed: 4 tests across desktop and narrow Chromium projects |
| Real-stack browser E2E | `apps/web/tests/e2e/sprint7.real.spec.ts`, `playwright.real.config.ts` | Passed: 1 test before restart and 1 test after restart on local Compose images |
| Clean Compose | `scripts/run_sprint7_acceptance.ps1`, `playwright.real.config.ts` | Services healthy; isolated containers/network cleaned after acceptance |
| Secret leak regression | DOM/storage assertion in E2E plus `scripts/check_secret_leaks.ps1` | Configured; scan requires supplied test secret |
| Compatibility/image | `scripts/run_sprint7_validation.ps1` plus production web Dockerfile/Compose override | Source checks run; Docker-dependent checks pending |
| Operations | local and operator runbooks | Complete |

## Validation evidence

The following configured checks passed during implementation:

```text
ruff check .                         # cwd apps/api
pyright src
python -m pytest -q              # 71 passed, 3 skipped (API virtualenv)
npm run format:check
npm run typecheck
npm run lint
npm run test
npm run check:api-drift
npm run build
```

The pinned Playwright package and Chromium runtime are installed. The
deterministic browser suite passed 4 tests across desktop and narrow projects.
The real-stack suite passed once before and once after API/web restart against
the Compose web/API/Semantic Core/Fuseki topology, with no LLM bootstrap
variables. The production web image build and development/production merged
Compose config checks passed.

## Known limitations and risks

- S7-47 product/security acceptance has not happened.
- Browser-facing knowledge, history, and evidence responses now use allowlisted
  opaque projections; RDF IRIs and raw provider-shaped payloads are not part of
  the public UI contract.
- First-run starts without `PROJECTA_LLM_*`; Settings creates the encrypted
  operational profile, while headless operations fail closed until configured.
- `run_sprint7_validation.ps1` now propagates native command failures instead of
  reporting false green completion. The API gate is 71 passed / 3 skipped in the
  repository virtualenv; an escalated uv run without the dev plugin is not used
  as evidence.
- The local experience adapter is not authentication or authorization.
- The production profile requires immutable `WEB_IMAGE`, `API_IMAGE`, and
  Semantic Core image references; no deployment secret manager integration is
  introduced in this sprint.
- A clean real-Compose Playwright run, plus human inspection of the trust and
  secret boundary, must be attached by the approver before M5 is marked
  complete.

## Approval request

Human reviewer should run the documented critical journey, inspect the secret
boundary and generated contract, and either approve M5 or return a concrete
revision request. Until then, S7-47 and M5 remain incomplete.
