# Task Summary: S10-45 — Installation APIs

Added project-scoped installation list/create/read/update/enable/disable routes
with finite pagination, revision checks, server-selected project scope, opaque
handles, and safe typed problem mapping. Public create/update input does not
accept raw secret references.

Testing: public API projection suite, API Pyright/Ruff, and web client checks passed.
