# Task Summary: S8-62 — Web information architecture

**Sprint:** Sprint 8
**Task:** S8-62
**Status:** Complete

## Outcome

The primary navigation now follows the approved Sprint 8 workspace IA:

`Projects → Project Overview → Notes → Graph → Review Queue → Q&A → Settings → Diagnostics`

Legacy Capture, Extract, and Knowledge screens remain in the repository for
compatibility with their existing API workflows, but are no longer shortcut
navigation destinations. The shell retains server-owned project selection,
opaque handles, skip-link navigation, `aria-current`, and responsive theme
behavior.

## Validation

- Navigation contract tests assert the exact ordered labels and reject legacy
  shortcut/identifier labels.
- `npm test` — passed: 12 tests.
- UI contract and frontend build validation are included in S8-63/S8-66.
