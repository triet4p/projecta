# Task Summary: S10-48 — API contract and generated client

Added connector paths to the curated Application API snapshot, regenerated
operation metadata, added typed TypeScript client methods, and kept trusted
server-auth headers out of the browser-facing contract.

Testing: `npm run check:api-drift` — passed with 47 public paths.
