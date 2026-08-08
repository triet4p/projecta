# S7-31 — Manual typed capture screen

Added selection-based typed span capture with ordered/non-overlapping checks,
exact evidence preview, released type allowlist, idempotent submit, and opaque
candidate navigation. Browser UTF-16 offsets are converted to API Unicode
code-point offsets.

Validation: emoji offset and overlap unit tests pass.
