# Sprint 12 G5 v8 Issuance Transition v21

**Role:** authoritative current G5 state

**Status:** `G5_F12_V8_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING`

RM-33 completed the separate owner issuance review and issued only the exact
v8 preregistration and technical-freeze lineage. This transition does not
authorize provider execution and does not mutate the immutable RM-32
preparation snapshots.

## Issued lineage

- lineage commit: `30f9fbff64eb02964b2661b7f468b27a81abb82e`
- exact runtime commit: `005a35e3be3fbff40fcdae02dfdf79145c76934b`
- preregistration and execution package digests remain bound by the RM-33
  owner review and issuance transition;
- the v8 output is reserved at
  `evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json` and is
  absent;
- immutable v6 report digest remains
  `sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`.

Authoritative machine packet:
`evaluation/sprint-12/optimization/g5-packet.v21.json`

Owner records:

- `evaluation/sprint-12/optimization/s12-f-12-rm33-owner-review.v1.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm33-issuance-transition.v1.json`

## Current boundary

The historical v7 lineage is the only issued/spent execution: one bounded
Stage A run made 144 provider calls and 96 relation-branch outputs, with zero
retries and `$0.00592500` cost. Current v8 has
`preregistrationIssued=true` and `technicalFreezeIssued=true`, but
`providerExecutionAuthorized=false`, `newAuthorizationIssued=false`, zero
authorized executions, zero provider calls and no report.

Validation, held-out access, Stage B, candidate selection and promotion remain
false. No accuracy, business-quality, tenant-readiness or human-evidence
claim is established.

## Next governed steps

1. RM-34 prepares the exact v8 Stage A authorization offline, binding the RM-33
   owner review and issuance transition, exact runtime commit, package/freeze
   digests, output path and cost ceiling.
2. RM-35 performs the separate owner authorization review.
3. No provider call or live runner is permitted before RM-35 authorization.
