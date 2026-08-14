# Sprint 12 Phase G Held-out Evaluation

**Status:** `G6_PREPARATION_BLOCKED_CUSTODY_OR_CANDIDATE`

The Phase G harness prepares a preregistration and verifies the sealed test
custody boundary before any payload can be opened. The repository-visible
custody manifest currently records `CUSTODY_NOT_ESTABLISHED` and
`payloadPresent: false`; therefore no held-out payload, reviewer text or
business result is stored here.

`scripts/sprint12_heldout.py` fails closed for missing custody, missing frozen
candidate, incomplete independent review and raw sensitive fields. The G6
packet is a preparation artifact, not a business-quality claim.
