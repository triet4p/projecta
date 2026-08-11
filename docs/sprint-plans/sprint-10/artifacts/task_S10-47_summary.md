# Task Summary: S10-47 — Connector public projections

Mapped internal installation/run rows into allowlisted DTOs with opaque handles,
safe states, safe failure codes, dead-letter availability, correlation, and
revision/timing fields. Event/replay counts and dead-letter availability are
persisted and remain truthful after refresh/restart. Internal IDs,
event/content references, SQL, storage,
RDF details, and exceptions are not returned.

Testing: response leak assertions and API contract gate passed.
