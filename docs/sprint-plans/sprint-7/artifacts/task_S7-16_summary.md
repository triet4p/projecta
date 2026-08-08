# S7-16 — Application-encrypted secret-store adapter

Implemented the provider-neutral `SecretStore` contract and Fernet-backed
application-encrypted adapter. Secret writes return opaque references, resolve
server-side, delete idempotently, and fail closed when the deployment master
key or ciphertext is unavailable.

Validation: ciphertext and unavailable-store regression tests pass.
