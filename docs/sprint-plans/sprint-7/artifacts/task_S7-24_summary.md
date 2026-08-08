# S7-24 — Local experience context adapter

Added an explicit experience-mode middleware that overwrites browser-selected
context with fixed server-owned project/actor context and a generated request
ID. Production mode does not inject local context and project routes fail
closed.

Validation: server-owned-context regression test passes.
