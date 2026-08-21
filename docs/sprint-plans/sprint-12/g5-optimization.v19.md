# Sprint 12 G5 Superseding Lineage Preparation v19 (Historical Snapshot)

**Role:** historical authoritative G5 state at RM-31

**Status:** `G5_F12_SUPERSEDING_LINEAGE_PREPARATION_APPROVED_OFFLINE_ONLY`

RM-31 approved the corrected RM-30 implementation and permits offline
preparation of a new exact-commit f12 preregistration, execution package and
technical-freeze packet. It does not issue any of those artifacts or authorize
a provider call.

## Bound implementation

The approved implementation remains the RM-30 versioned sanitized diagnostic
path and deterministic mock evidence. It preserves the immutable Stage A
report digest:

`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`

The historical v7 lineage retains its factual record: preregistration and
technical freeze were issued, one 144-call Stage A execution ran, and retry
count was zero. These are historical facts, not issuance of the superseding
lineage.

## Current authorization boundary

- `supersedingLineagePreparationAuthorized=true`
- `preregistrationPreparationAuthorized=true`
- `technicalFreezePreparationAuthorized=true`
- `executionPackagePreparationAuthorized=true`
- `preregistrationIssued=false`
- `technicalFreezeIssued=false`
- `providerExecutionAuthorized=false`
- `newAuthorizationIssued=false`
- validation, held-out access, Stage B, candidate selection and promotion remain false

RM-32 may create the new versioned preparation artifacts offline. Separate
owner issuance review is required before preregistration or freeze issuance,
and separate execution authorization is required before any provider call.
No accuracy improvement, business-quality result or candidate selection is
established.

Historical machine packet:

`evaluation/sprint-12/optimization/g5-packet.v19.json`
