# S7-30 — Quick Note extraction screen

Added raw-note extraction with line-ending normalization, idempotent submission,
candidate navigation, entity/relation/link rendering, exact evidence offsets,
and explicit abstention display. The backend now returns normalized M3 details
alongside opaque lifecycle results.

Validation: backend regression suite and frontend type/build gates pass.
