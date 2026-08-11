# Task Summary: S10-65 — Tag release workflow extension

Extended `.github/workflows/release.yml` with required Sprint 10 validation,
clean acceptance, recovery, frontend-format, and connector-security jobs.
`publish.needs` now includes every new job, with no `continue-on-error`,
`if: always()`, or release bypass. Chromium installation is explicit in the
browser-bearing CI jobs.

Testing: release-workflow contract tests passed.
