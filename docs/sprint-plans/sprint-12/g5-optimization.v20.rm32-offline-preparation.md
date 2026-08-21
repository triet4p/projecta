# Sprint 12 G5 RM-32 Offline Lineage Preparation v20

**Role:** non-authoritative offline next-state preparation

**Current authoritative packet:**
`evaluation/sprint-12/optimization/g5-packet.v21.json`

This v20 document is an immutable RM-32 preparation snapshot. RM-33 later
issued the reviewed v8 preregistration and technical freeze through a separate
transition; the unissued fields in the RM-32 files and this historical account
are not rewritten.

RM-32 prepared a new versioned v8 f12 preregistration, execution package,
technical freeze and provider-neutral zero-call preflight under the RM-31
approval boundary. The runtime commit contains a guarded v8 runner that calls
the RM-30 finite classifiers for new response failures and persists sanitized
reason counts under closed v8 report/authorization schemas.

Runtime bindings use exact git-blob SHA-256 bytes. Preflight and tests are
separate preparation evidence and are excluded from the runtime digest set;
their physical presence at the execution commit is not an execution claim.

The v8 report schema now applies a closed sanitized-key policy to every
ontology-keyed metric map, including casing and separator variants of the
registered raw-payload/source/evidence aliases. Deterministic mocked regression
coverage injects each forbidden alias recursively and preserves validation of
legitimate entity and predicate keys.

## Prepared artifacts

- `evaluation/sprint-12/optimization/s12-f-12-rm32-preregistration.v8.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm32-technical-freeze.v8.json`
- `scripts/preflight_sprint12_f12_rm32.py`

The preflight result is `F12_RM32_READY_ZERO_CALL` with `providerCalls=0`.
The new output is reserved at
`evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json`; the
immutable v6 report remains untouched.

## Governance boundary

At RM-32 preparation time, preparation flags were true and
`preregistrationIssued=false`,
`technicalFreezeIssued=false`, `providerExecutionAuthorized=false`,
`newAuthorizationIssued=false`, and validation, held-out access, Stage B,
selection and promotion remain false. RM-33 must review and issue the prepared
artifacts; a separate exact-commit authorization is required before execution.
