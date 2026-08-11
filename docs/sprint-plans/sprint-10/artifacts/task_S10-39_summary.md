# Task Summary: S10-39 — Map canonical events to source drafts

Implemented bounded JSON/Mock event mapping into the released `CaptureRequest`
contract. Connector imports carry `sourceKind=connector`, the canonical event
content hash, server-owned actor/project context, and exact NoteItem offsets.
Malformed or unsupported content abstains with finite codes.

Testing: source-mapping focused tests, Ruff, and strict Pyright passed.
