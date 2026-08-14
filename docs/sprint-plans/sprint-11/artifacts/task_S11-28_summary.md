# Task Summary: S11-28 — Authenticated browser shell

**Sprint:** Sprint 11
**Task:** S11-28

## Summary of Work
Added a browser auth gate with sign-in redirect, signed-in server-state presentation, same-origin session calls, logout, and session-expired recovery. Raw claims and provider tokens are never rendered or persisted by the client.

## Files Modified
* [apps/web/src/shell/AuthShell.tsx](../../../../apps/web/src/shell/AuthShell.tsx)
* [apps/web/src/shell/App.tsx](../../../../apps/web/src/shell/App.tsx)
* [apps/web/src/api/client.ts](../../../../apps/web/src/api/client.ts)

## Testing
* **Test File:** Web existing suite
* **Status:** Passed
* **Execution Command:** `npm test -- --run` and `npm run build`

## Additional Notes
Non-production session endpoint returns an unauthenticated state so local experience remains explicit rather than silently selecting a provider.
