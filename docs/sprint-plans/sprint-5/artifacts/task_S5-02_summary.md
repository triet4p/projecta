# Task Summary: S5-02 — Define the extraction error taxonomy

**Sprint:** Sprint 5
**Task:** S5-02

## Summary of Work

Defined stable normalized classes for malformed schema, unsupported ontology
values, evidence and link failures, abstention, timeout, rate limiting,
provider/configuration failure, normalization, semantic validation, project
context, idempotency, and unexpected failure. Each class has retry and
persistence semantics plus safe public API mapping.

## Files Modified

- `docs/architecture/llm-extraction-errors.md` — M3 error taxonomy and safety rules.

## Testing

- **Test File:** Not applicable; this task establishes a cross-boundary contract.
- **Status:** `git diff --check` passed.
- **Execution Command:** `git -c safe.directory=F:/ai-ml/projecta diff --check`
