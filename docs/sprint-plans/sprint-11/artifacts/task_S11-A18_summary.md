# Task Summary: S11-A18 — Disposable Public Repository Journey

## Status

`DONE — V2 EVIDENCE REGENERATED`

## Preparation completed

Using the authorized `gh` account `triet4p`, created the disposable public
repository `projecta-s11-github-acceptance-20260813-r4` and seeded only fabricated
acceptance data:

- two baseline issues and two baseline issue comments;
- one additional edited issue and one additional edited issue comment;
- one fabricated pull request for exclusion verification.

Unauthenticated GitHub REST verification returned three baseline issue-shaped
records, one of which was the pull request object, and two baseline comments.
No GitHub token was used by Projecta for this verification.

## Blocker

The credential-free runner completed against the local production-shaped API
and connector PostgreSQL stack. It selected the server-owned project catalog,
created and enabled one GitHub Public Issues installation, imported events,
then disabled the installation. The extended journey also verified an edit
produced new events, idempotent replay returned `replayed`, a forged project
handle returned HTTP 404, and the fabricated pull request was excluded.

The executable v2 producers generated sanitized evidence. Baseline imported 4
events; the edit lifecycle imported 2 events before and 2 after edit; exact
replay returned `replayed`; candidate/evidence continuity and forged-project
HTTP 404 were observed. Sanitized evidence is in:

- `s11-A18-github-live-acceptance.json`
- `s11-A18-github-live-journey.json`

No GitHub credential was passed to Projecta or persisted. The disposable
repository was archived after acceptance evidence review.
