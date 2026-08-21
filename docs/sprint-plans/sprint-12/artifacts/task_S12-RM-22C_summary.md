# S12-RM-22C summary

Status: `COMPLETED_OFFLINE_REMEDIATION_READY_FOR_RM23C_OWNER_REVIEW`

RM-22C supersedes the withheld RM-22B lineage without modifying historical v1-v3 artifacts. The v4 offline runner and custody layer now:

- materialize the gold relation trigger from frozen source text, including the Vietnamese `constrainedBy` mapping, with zero gold-oracle materializer failures;
- derive relation-negative membership from frozen gold (`4 cases × 3 runs = 12`) separately from abstention-required cases (`4 cases × 3 runs = 12`);
- apply thresholds only when the corresponding metric has an applicable denominator, while preserving numeric hard and slice gates;
- require the closed v4 report JSON Schema and fail closed when `jsonschema` is unavailable;
- require exact `experimentId=s12-f-12` and false held-out, Stage B, selection and promotion guards before any provider capture;
- bind package, preregistration, freeze, runner, schema, preflight and exact-commit blobs to commit `de1589e7d67249ddbcbb48dc6bde6edf7fa03362`.

Validation evidence:

- RM-22C targeted tests: `3 passed`;
- f12 regression set: `47 passed`;
- preflight: `F12_RM22C_READY_ZERO_CALL_V4`;
- derived denominators: relation `24`, relation-negative `12`, abstention-required `12`;
- Ruff, JSON validation and `git diff --check`: pass;
- provider calls: `0`; held-out access: `false`;
- no Stage A output or authorization artifact was created.

Governance: preregistration, execution package and technical freeze remain prepared-only. RM-23C owner issuance review is required next. Any provider execution still requires a separate exact-commit authorization.
