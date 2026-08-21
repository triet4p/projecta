# Sprint 12 G5 — RM-43 Corrected v9 Issuance

**Status:** `G5_F12_CORRECTED_V9_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING`

RM-43 completed the separate owner issuance review for the corrected RM-42 v9
lineage. It issued only the exact v9 preregistration and technical freeze;
provider execution still requires a new exact authorization and a separate
owner review.

## Immutable decision records

- `evaluation/sprint-12/optimization/s12-f-12-rm43-owner-review.v1.json`
  (`sha256:dd8d0210e8bed24b68fea64188fd8bb5cbb45c7a5962f4342b74b8811c9006a9`)
- `evaluation/sprint-12/optimization/s12-f-12-rm43-issuance-transition.v1.json`
  (`sha256:d57f040293ff0be4573d49e97a20cea9c838152b47945ee3fc01af2568637fdb`)
- `evaluation/sprint-12/optimization/g5-packet.v29.rm43-issuance.json`

The issued lineage binds the RM-42 package, preregistration and freeze at
execution commit `f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`. Its runtime
custody remains 19 exact Git blobs; working-tree line endings are not used as
canonical runtime evidence.

## Evidence and preservation

The RM-42 preflight remains `F12_RM42_READY_ZERO_CALL`: zero provider calls,
zero retries, 144 planned provider calls, 96 planned relation branches and no
v9 output. RM-43 added a provider-neutral issuance preflight at
`scripts/preflight_sprint12_f12_rm43.py`.

The v6 report remains immutable at
`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`.
The failed v8 invocation remains preserved as a superseded lineage fact; both
the failed v8 report and the v9 report are absent.

## Governance boundary

Only `preregistrationIssued` and `technicalFreezeIssued` are true for the
current v9 lineage. Provider execution, new authorization, rerun, retry,
validation, held-out access, Stage B, candidate selection and promotion remain
false. No quality improvement, candidate, business-quality or tenant-readiness
claim is established.

## Next gates

1. **S12-RM-44:** prepare exact v9 Stage A authorization offline.
2. **S12-RM-45:** independently review and issue the authorization before any
   provider call.
