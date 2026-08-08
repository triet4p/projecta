# S7-18 — Redacted settings read API

Added `GET /v1/settings/llm`, returning provider metadata, active revision,
health, and credential status only. Raw credentials and secret references are
excluded from the public response.

Validation: settings boundary test confirms redaction.
