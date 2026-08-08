# S7-37 summary

- Added multi-stage `apps/web/Dockerfile` producing a static Nginx runtime image.
- Added same-origin Nginx proxying for `/v1` and `/health` only.
- Added Compose `web` profile, API/web health checks, dev port, and production immutable `WEB_IMAGE` override.
