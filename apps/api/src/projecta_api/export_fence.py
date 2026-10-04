"""Process-wide writer fence for cross-store portable export snapshots."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

_EXPORT_PATH = re.compile(r"^/v1/projects/[^/]+/exports$")
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class ExportAlreadyRunning(RuntimeError):
    """Another portable export owns the project-wide no-writer epoch."""


class ProjectWriteFence:
    """Exclude API writers while one bounded multi-store snapshot is collected."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._active_writers = 0
        self._exporting = False
        self._write_attempted = False

    async def enter_write(self) -> bool:
        async with self._condition:
            if self._exporting:
                self._write_attempted = True
                return False
            self._active_writers += 1
            return True

    async def exit_write(self) -> None:
        async with self._condition:
            if self._active_writers < 1:
                raise RuntimeError("project write fence accounting is inconsistent")
            self._active_writers -= 1
            if self._active_writers == 0:
                self._condition.notify_all()

    @asynccontextmanager
    async def export_epoch(self) -> AsyncIterator[None]:
        async with self._condition:
            if self._exporting:
                raise ExportAlreadyRunning()
            self._exporting = True
            self._write_attempted = False
            try:
                await self._condition.wait_for(lambda: self._active_writers == 0)
            except BaseException:
                self._exporting = False
                self._condition.notify_all()
                raise
        try:
            yield
        except BaseException:
            async with self._condition:
                self._exporting = False
                self._condition.notify_all()
            raise
        else:
            async with self._condition:
                write_attempted = self._write_attempted
                self._exporting = False
                self._condition.notify_all()
            if write_attempted:
                raise ExportWriteAttempted()

    async def ensure_no_write_attempts(self) -> None:
        async with self._condition:
            if self._exporting and self._write_attempted:
                raise ExportWriteAttempted()


class ExportWriteAttempted(RuntimeError):
    """A mutating request arrived during the frozen export epoch."""


 


class ProjectWriteFenceMiddleware(BaseHTTPMiddleware):
    """Reject new mutating Application API requests during the export epoch."""

    def __init__(self, app: object, fence: ProjectWriteFence) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._fence = fence

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if (
            request.url.path.startswith("/v1/")
            and request.method in _MUTATING_METHODS
            and _EXPORT_PATH.fullmatch(request.url.path) is None
        ):
            if not await self._fence.enter_write():
                request_id = getattr(request.state, "request_id", "unknown")
                return JSONResponse(
                    status_code=409,
                    media_type="application/problem+json",
                    content={
                        "type": "about:blank",
                        "title": "Project export in progress",
                        "status": 409,
                        "detail": "A project export is collecting a consistent snapshot. Retry after it completes.",
                        "code": "EXPORT_BUSY",
                        "requestId": request_id,
                    },
                )
            try:
                return await call_next(request)
            finally:
                await self._fence.exit_write()
        return await call_next(request)
