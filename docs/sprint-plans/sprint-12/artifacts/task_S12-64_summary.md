# S12-64 — Reviewer utility capture

Added aggregate disposition, correction-class, review-time, usefulness and
trust capture. Raw source text, answer text and reviewer comments are rejected.

## Testing

The Phase E self-tests reject a record containing `sourceText` and accept a
sanitized aggregate record.
