# Task Summary: Align the web extraction timeout budget / S7-46A

**Sprint:** Sprint 7 / M5 Web Experience
**Task:** S7-46A

## Summary of Work

Aligned the Nginx same-origin API proxy timeout with the Application API's
bounded Quick Note extraction retry budget. A slow provider can now complete all
bounded attempts and let the API return either a successful extraction or its
sanitized problem response instead of Nginx returning a premature 504 after 60
seconds.

## Files Modified

- `apps/web/nginx.conf` - Configured a 210-second API proxy read/send budget.
- `apps/web/scripts/check-nginx-config.mjs` - Added a regression gate for the
  minimum bounded extraction budget.
- `apps/web/package.json` - Exposed the Nginx regression gate as an npm command.
- `scripts/run_sprint7_validation.ps1` - Included the gate in canonical Sprint 7
  validation.
- `CHANGELOG.md` - Recorded the user-visible timeout fix.
- `.agents/memory/lessons-learned.md` - Recorded the reusable timeout-boundary
  lesson.
- `docs/sprint-plans/sprint-7.md` - Marked S7-46A complete without changing the
  pending human M5 approval gate.

## Testing

- **Test File:** `apps/web/scripts/check-nginx-config.mjs`
- **Status:** Passed
- **Execution Command:** `npm run check:nginx-config`
- **Additional Validation:** `npm run format:check`, `npm run lint`,
  `npm run typecheck`, `npm run test`, `npm run build`, and Nginx 1.29
  `nginx -t` all passed.

## Additional Notes

- The API retains its existing three-attempt, 60-second-per-attempt bounded
  provider policy; this task changes only the outer web proxy budget.
- At task completion, S7-47 remained pending explicit human product and security acceptance; the later approval is recorded in the review packet.
