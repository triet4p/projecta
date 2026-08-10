# Task Summary: Preserve server-owned response correlation

**Sprint:** Sprint 9 — Provider Runtime Truthfulness
**Task:** S9-10

## Summary of Work

Removed the Nginx override that replaced API-authored correlation headers with
the browser ingress ID. Proxied API responses now preserve the server-owned
`X-Request-Id`, while Nginx-authored timeout responses continue to use the
ingress ID in both the problem body and header.

## Files Modified

* [apps/web/nginx.conf](../../../../apps/web/nginx.conf) - Preserve upstream API
  correlation headers on ordinary proxied responses.
* [apps/web/scripts/check-nginx-config.mjs](../../../../apps/web/scripts/check-nginx-config.mjs)
  - Reject future response-header overrides in `/v1/` and verify the timeout-only
  correlation behavior.
* [docs/sprint-plans/sprint-9.md](../sprint-9.md) - Track completion of S9-10.
* [.agents/memory/lessons-learned.md](../../../../.agents/memory/lessons-learned.md)
  - Record the proxy correlation-boundary regression.

## Testing

* **Test File:** [apps/web/scripts/check-nginx-config.mjs](../../../../apps/web/scripts/check-nginx-config.mjs)
* **Status:** Passed
* **Execution Command:** `npm run check:nginx-config && npm test && npm run typecheck && npm run lint`
* **Runtime Verification:** Nginx syntax passed; after container reload,
  `GET /v1/projects?limit=50` returned HTTP 200 with matching server-owned
  `X-Request-Id` header and JSON `requestId`, plus two catalog projects.

## Additional Notes

The client-supplied correlation value remains an ingress hint. In experience
mode, the API middleware deliberately replaces it with a server-owned
`experience-*` identity. Nginx must not overwrite that upstream response value.
