# S7-21 — Provider connection check

Added bounded OpenAI-compatible model-list connectivity checks with timeout,
sanitized health outcomes, and no provider response payload in the result or
audit event.

Validation: provider-neutral connection contract is type-checked and exposed
through the settings route.
