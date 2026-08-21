# Sprint 12 G5 RM-34 Exact v8 Authorization Preparation v22

**Role:** non-authoritative authorization-preparation snapshot

**Authoritative packet remains:**
`evaluation/sprint-12/optimization/g5-packet.v21.json`

RM-34 prepared an exact v8 Stage A authorization offline. The preparation is
not an issued authorization: provider execution, new authorization, output,
validation, held-out access, Stage B, selection and promotion remain closed.

## Bound preparation

`evaluation/sprint-12/optimization/s12-f-12-rm34-authorization-preparation.v1.json`

The artifact binds:

- RM-33 owner review and issuance transition digests;
- lineage commit `30f9fbff64eb02964b2661b7f468b27a81abb82e` and exact execution
  commit `005a35e3be3fbff40fcdae02dfdf79145c76934b`;
- RM-32 v8 preregistration, execution-package and technical-freeze digests;
- 22 runtime git-blob bindings, runner, authorization/report schemas, runtime
  configuration, model, prompt, provider adapter, dataset and output path;
- exactly 144 planned provider calls, 96 relation branches, no retry, no
  overwrite and a strict `$10.00` ceiling.

The zero-call preflight is
`F12_RM34_PREPARED_ZERO_CALL`. Existing deterministic mocked coverage proves
the unauthorized path makes zero calls and the prospective authorized path
would make 144 calls/96 branches, persist once, retry zero times and reject
overwrite. No real provider or live runner was invoked.

## Reconciliation required before RM35

The immutable RM-33 owner review records report-schema digest
`sha256:662e36911f16aa01c7eda920ec57c4fa9890ad47a4c4e4da2ef9a526482a17fc`,
but the exact execution-commit blob is
`sha256:c65a4f039d948e6f3a59750001e58199bfc98e57e2f2f3ac838070ef5f6f6ad5`.
RM-34 binds the exact execution blob and exposes this mismatch; it does not
silently authorize around it. RM-35 must reconcile the binding before issuing
any v8 authorization.

Non-authoritative snapshots:

- `evaluation/sprint-12/current-state-next-rm34.v1.json`
- `evaluation/sprint-12/optimization/g5-packet.v22.rm34-authorization-preparation.json`
