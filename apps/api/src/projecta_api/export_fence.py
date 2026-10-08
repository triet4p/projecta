"""Process-wide writer fence for cross-store portable export snapshots."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

_EXPORT_PATH = re.compile(r"^/v1/projects/[^/]+/exports$")
_IMPORT_APPLY_PATH = re.compile(r"^/v1/imports/previews/[^/]+/apply$")
_DELETION_PATH = re.compile(r"^/v1/projects/deletion/(preview|delete)$")
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class ExportAlreadyRunning(RuntimeError):
    """Another portable export owns the project-wide no-writer epoch."""


class ProjectWriteFence:
    """Exclude API writes and reads while a project maintenance operation publishes cross-store state."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._active_writers = 0
        self._active_readers = 0
        self._exporting = False
        self._maintenance_kind = ""
        self._write_attempted = False
        self._recovery_required = False

    async def enter_write(self) -> bool:
        async with self._condition:
            if self._recovery_required or self._exporting:
                if self._maintenance_kind == "export":
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

    async def enter_read(self) -> bool:
        async with self._condition:
            if self._recovery_required or self._maintenance_kind == "import":
                return False
            self._active_readers += 1
            return True

    async def exit_read(self) -> None:
        async with self._condition:
            if self._active_readers < 1:
                raise RuntimeError("project read fence accounting is inconsistent")
            self._active_readers -= 1
            if self._active_readers == 0:
                self._condition.notify_all()

    async def require_recovery(self) -> None:
        async with self._condition:
            self._recovery_required = True
            self._condition.notify_all()

    @asynccontextmanager
    async def export_epoch(self) -> AsyncGenerator[None]:
        async with self._condition:
            if self._recovery_required or self._exporting:
                raise ExportAlreadyRunning()
            self._exporting = True
            self._maintenance_kind = "export"
            self._write_attempted = False
            try:
                await self._condition.wait_for(lambda: self._active_writers == 0)
            except BaseException:
                self._exporting = False
                self._maintenance_kind = ""
                self._condition.notify_all()
                raise
        try:
            yield
        except BaseException:
            async with self._condition:
                self._exporting = False
                self._maintenance_kind = ""
                self._condition.notify_all()
            raise
        else:
            async with self._condition:
                write_attempted = self._write_attempted
                self._exporting = False
                self._maintenance_kind = ""
                self._condition.notify_all()
            if write_attempted:
                raise ExportWriteAttempted()

    @asynccontextmanager
    async def maintenance_epoch(self) -> AsyncGenerator[None]:
        """Drain API requests and exclude all project access during import publication."""
        async with self._condition:
            if self._recovery_required or self._exporting:
                raise ExportAlreadyRunning()
            self._exporting = True
            self._maintenance_kind = "import"
            self._write_attempted = False
            try:
                await self._condition.wait_for(
                    lambda: self._active_writers == 0 and self._active_readers == 0
                )
            except BaseException:
                self._exporting = False
                self._maintenance_kind = ""
                self._condition.notify_all()
                raise
        try:
            yield
        finally:
            async with self._condition:
                self._exporting = False
                self._maintenance_kind = ""
                self._condition.notify_all()

    @asynccontextmanager
    async def deletion_epoch(self) -> AsyncGenerator[None]:
        """Drain API requests and exclude all project access during project deletion."""
        async with self._condition:
            if self._recovery_required or self._exporting:
                raise ExportAlreadyRunning()
            self._exporting = True
            self._maintenance_kind = "deletion"
            self._write_attempted = False
            try:
                await self._condition.wait_for(
                    lambda: self._active_writers == 0 and self._active_readers == 0
                )
            except BaseException:
                self._exporting = False
                self._maintenance_kind = ""
                self._condition.notify_all()
                raise
        try:
            yield
        finally:
            async with self._condition:
                self._exporting = False
                self._condition.notify_all()

    async def busy_code(self) -> str:
        async with self._condition:
            if self._recovery_required:
                return "IMPORT_RECOVERY_REQUIRED"
            if self._maintenance_kind == "import":
                return "IMPORT_BUSY"
            if self._maintenance_kind == "deletion":
                return "DELETE_BUSY"
            return "EXPORT_BUSY"

    async def recovery_required(self) -> bool:
        async with self._condition:
            return self._recovery_required


    async def ensure_no_write_attempts(self) -> None:
        async with self._condition:
            if self._exporting and self._write_attempted:
                raise ExportWriteAttempted()


class ExportWriteAttempted(RuntimeError):
    """A mutating request arrived during the frozen export epoch."""


class _FencedResponse(Response):
    """Response carrying the drained streaming body the fence must keep open."""

    body_iterator: AsyncIterator[bytes]


class ProjectWriteFenceMiddleware(BaseHTTPMiddleware):
    """Fence project API traffic during maintenance and reject fatal recovery states."""

    def __init__(self, app: object, fence: ProjectWriteFence) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._fence = fence

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)

        if await self._fence.recovery_required():
            return _maintenance_response(request, "IMPORT_RECOVERY_REQUIRED")

        if _IMPORT_APPLY_PATH.fullmatch(request.url.path) is not None:
            return await call_next(request)

        if _DELETION_PATH.fullmatch(request.url.path) is not None:
            return await call_next(request)

        if (
            request.method in _MUTATING_METHODS
            and _EXPORT_PATH.fullmatch(request.url.path) is None
        ):
            if not await self._fence.enter_write():
                return _maintenance_response(request, await self._fence.busy_code())
            try:
                return await call_next(request)
            finally:
                await self._fence.exit_write()

        if not await self._fence.enter_read():
            return _maintenance_response(request, await self._fence.busy_code())
        release_read = True
        try:
            response = await call_next(request)
            fenced = cast(_FencedResponse, response)
            raw_iterator: object = getattr(fenced, "body_iterator", None)
            if raw_iterator is None:
                await self._fence.exit_read()
                release_read = False
                return response
            if not isinstance(raw_iterator, AsyncIterator):
                await self._fence.exit_read()
                release_read = False
                return response
            body_iterator: AsyncIterator[bytes] = cast(AsyncIterator[bytes], raw_iterator)

            async def stream_body() -> AsyncIterator[bytes]:
                try:
                    async for chunk in body_iterator:
                        yield chunk
                finally:
                    await self._fence.exit_read()

            fenced.body_iterator = stream_body()
            release_read = False
            return response
        finally:
            if release_read:
                await self._fence.exit_read()


def _maintenance_response(request: Request, code: str) -> JSONResponse:
    recovery_required = code == "IMPORT_RECOVERY_REQUIRED"
    return JSONResponse(
        status_code=503 if recovery_required else 409,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": (
                "Project import recovery required"
                if recovery_required
                else "Project maintenance in progress"
            ),
            "status": 503 if recovery_required else 409,
            "detail": (
                "Project import recovery is required before this runtime can serve requests."
                if recovery_required
                else "A project maintenance operation is excluding project access. Retry after it completes."
            ),
            "code": code,
            "requestId": getattr(request.state, "request_id", "unknown"),
        },
    )
