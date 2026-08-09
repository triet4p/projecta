# Task Summary: Web invalid-response rejection

**Sprint:** Sprint 8
**Task:** S8-23

## Summary of Work

Hardened the Web API client to require a response request ID, approved JSON
content type, valid JSON, a complete RFC 7807 problem body for errors, and a
typed success envelope for health, collections, and Quick Note responses.
Non-JSON, missing-correlation, malformed-problem, schema-drift, and malformed
success responses now raise explicit `CLIENT_RESPONSE_INVALID` errors instead
of becoming `{}`, generic HTTP errors, or silent success casts.

## Files Modified

* [client.ts](../../../../apps/web/src/api/client.ts) - Strict response parsing, problem validation, and success shape checks.
* [client.test.ts](../../../../apps/web/src/api/client.test.ts) - Non-JSON/malformed-success regressions and correlation headers.

## Testing

* **Test File:** [client.test.ts](../../../../apps/web/src/api/client.test.ts)
* **Status:** Passed.
* **Execution Command:** `npm test -- --run`; `npm run typecheck`

## Additional Notes

The client still preserves server-provided finite problem codes and request IDs;
it no longer manufactures a generic `HTTP_ERROR` for malformed API problems.
