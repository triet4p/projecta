# S12-RM-22D summary

Status: `COMPLETED_OFFLINE_REMEDIATION_READY_FOR_RM23D_OWNER_REVIEW`

RM-22D publishes a superseding v5 lineage and preserves RM-22C and earlier artifacts as historical evidence. The accepted oracle, denominator and applicability logic are unchanged. The new boundary adds:

- a report schema whose ordered `sliceRecords` bind the exact 15 preregistered dimension/label/denominator tuples;
- exact preregistered threshold constants for every threshold field;
- a closed authorization schema with `additionalProperties=false`, exact experiment/schedule/commit/package/freeze/output/cost fields, and explicit false locks for validation, held-out, Stage B, selection and promotion;
- strict authorization validation before any provider capture, with missing `jsonschema` failing closed;
- adversarial tests for slice label, denominator, threshold, unknown-field and expanded-authority tampering.

Validation evidence:

- RM-22D targeted tests: `5 passed`;
- full f12 regression: `52 passed`;
- preflight: `F12_RM22D_READY_ZERO_CALL_V5`;
- derived denominators: relation `24`, relation-negative `12`, abstention-required `12`;
- Ruff, JSON Schema validation and `git diff --check`: pass;
- provider calls: `0`; held-out access: `false`;
- no Stage A output or authorization artifact was created.

Governance: preregistration, execution package and technical freeze remain prepared-only. RM-23D owner issuance review is required next. Provider execution still requires a separate exact-commit authorization.
