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

The RM32 preflight binding is corrected to its exact Git-blob digest
`sha256:492cc4c9815c168233039c096d5f7bc6121773a2b7f6f84443ed587fea1f8d3e`.
RM-34's own preflight is intentionally excluded from the 22 runtime blobs and
is checked through external preparation evidence with digest mode
`working_tree_sha256` and digest
`sha256:ed78c94f97f9ed866a58779541d2bac6178adc0ab58741c40909c5c6413c5e63`.
This avoids a self-referential preparation digest while making one-character
tampering fail closed.

The zero-call preflight is
`F12_RM34_PREPARED_ZERO_CALL`. Existing deterministic mocked coverage proves
the unauthorized path makes zero calls and the prospective authorized path
would make 144 calls/96 branches, persist once, retry zero times and reject
overwrite. Regression tests reject both the prior RM32 preflight digest typo
and an RM34 preflight tamper. No real provider or live runner was invoked.

## Custody reconciliation and RM35

The immutable RM-33 owner review records report-schema digest
`sha256:662e36911f16aa01c7eda920ec57c4fa9890ad47a4c4e4da2ef9a526482a17fc`,
and the exact execution-commit blob is
`sha256:c65a4f039d948e6f3a59750001e58199bfc98e57e2f2f3ac838070ef5f6f6ad5`.
The accepted RM33 custody erratum records that the difference is CRLF-to-LF
normalization only and that normalized content is equal. RM-34 binds the
canonical execution blob; provider execution and new authorization remain
false until RM-35 independently reviews and acts.

Non-authoritative snapshots:

- `evaluation/sprint-12/current-state-next-rm34.v1.json`
- `evaluation/sprint-12/optimization/g5-packet.v22.rm34-authorization-preparation.json`
