# Task Summary: Nginx structured access/error logs

**Sprint:** Sprint 8
**Task:** S8-21

## Summary of Work

Added an Nginx `s8.logging.v1` JSON access log and explicit stderr error log.
The proxy records safe request/operation correlation, allowlisted route class,
method, status, request/upstream timing, upstream status/address, and
connection identity without request line, body, query, credentials, or trusted
headers. The API proxy timeout gate now reflects the approved single-attempt
provider budget.

## Files Modified

* [nginx.conf](../../../../apps/web/nginx.conf) - Correlation maps, route class map, structured access/error logs, and 70-second proxy budget.
* [check-nginx-config.mjs](../../../../apps/web/scripts/check-nginx-config.mjs) - Timeout and log-safety assertions.

## Testing

* **Test File:** [check-nginx-config.mjs](../../../../apps/web/scripts/check-nginx-config.mjs)
* **Status:** Passed.
* **Execution Command:** `npm run check:nginx-config`

## Additional Notes

Nginx access logging intentionally does not serialize `$request`, request
bodies, query strings, cookies, or trusted context headers.
