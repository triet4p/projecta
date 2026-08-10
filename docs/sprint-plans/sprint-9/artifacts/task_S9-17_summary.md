# Task Summary: Publish and verify v0.4.0

**Sprint:** Sprint 9 — Provider Runtime Truthfulness
**Task:** S9-17

## Summary of Work

Committed and pushed the release contract, created and pushed annotated tag
`v0.4.0`, followed the tag-triggered GitHub Actions run through every required
job, and verified the resulting public GitHub Release is neither a draft nor a
prerelease.

After publication, updated the release workflow to the current major versions
of GitHub's official checkout/setup actions so future tag runs do not inherit
the Node 20 deprecation warnings observed during the 0.4.0 run.

## Publication Evidence

* Release commit: `0b36a3eefdd7efa126e44de25a3653f3ebc30c27`
* Tag: `v0.4.0`
* Workflow: <https://github.com/triet4p/projecta/actions/runs/31364894282>
* Release: <https://github.com/triet4p/projecta/releases/tag/v0.4.0>
* Published: 2026-08-10T07:15:41Z

## GitHub Validation

* Release contract, API, web, Semantic Core, repository contracts, and system
  jobs all completed successfully.
* The clean-volume system job completed in 3 minutes 19 seconds.
* Publish rendered notes from `CHANGELOG.md` and created `Projecta 0.4.0`.

## Additional Notes

The release workflow remains tag-only and continues to require exact `vA.B.C`
validation before publication.
