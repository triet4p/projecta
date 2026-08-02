# S5-32A — DeepSeek Responses compatibility and live reliability

Fixed the live provider path using the official DeepSeek Responses API contract:

- the required base URL is supplied through `PROJECTA_LLM_BASE_URL`;
- the required Responses model is supplied through `PROJECTA_LLM_MODEL`;
- removed the unsupported `store` request field;
- replaced the placeholder response schema with a strict fully-required nested schema;
- added a 60-second extraction timeout and bounded retry for transient live calls;
- added provider compatibility regression coverage.

Verification: with all four required `PROJECTA_LLM_*` variables supplied from `.env`, the focused previously failing relation case completed successfully, followed by a full live run of all 8 cases with `completed: 8`, no error classes, and exit code 0.
