"""Typed project catalog, overview, and server-side selection contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["active", "paused", "archived"]
Health = Literal["fresh", "attention", "unavailable"]
FreshnessState = Literal["current", "stale", "unavailable"]


class ProjectCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: int = Field(ge=0)
    tasks: int = Field(ge=0)
    questions: int = Field(ge=0)
    risks: int = Field(ge=0)
    notes: int = Field(ge=0)
    candidates: int = Field(ge=0)


class ProjectFreshness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: FreshnessState
    revision: str | None = None


class ProjectCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: str = Field(min_length=8, max_length=96)
    name: str = Field(min_length=1, max_length=160)
    summary: str | None = Field(default=None, max_length=500)
    status: Status
    counts: ProjectCounts
    last_activity_at: datetime | None = Field(default=None, alias="lastActivityAt")
    health: Health
    freshness: ProjectFreshness


class ProjectCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request_id: str = Field(alias="requestId")
    catalog_revision: str = Field(alias="catalogRevision", min_length=8, max_length=128)
    projects: list[ProjectCatalogItem]
    next_cursor: str | None = Field(default=None, alias="nextCursor")


class ProjectReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request_id: str = Field(alias="requestId")
    project: ProjectCatalogItem


class ProjectOverviewResponse(ProjectCatalogItem):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request_id: str = Field(alias="requestId")
    current_requirements: list[dict[str, str]] = Field(alias="currentRequirements")
    open_questions: list[dict[str, str]] = Field(alias="openQuestions")
    tasks: list[dict[str, str]]
    blockers: list[dict[str, str]]
    risks: list[dict[str, str]]
    recent_notes: list[dict[str, str]] = Field(alias="recentNotes")
    pending_candidates: list[dict[str, str]] = Field(alias="pendingCandidates")
    evidence_coverage: dict[str, int] = Field(alias="evidenceCoverage")


class ProjectSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    handle: str = Field(min_length=8, max_length=96)
    catalog_revision: str = Field(alias="catalogRevision", min_length=8, max_length=128)


class ProjectSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request_id: str = Field(alias="requestId")
    selection_revision: str = Field(alias="selectionRevision", min_length=8, max_length=128)
    project: ProjectCatalogItem


def configured_project_ids(raw: str) -> tuple[str, ...]:
    """Parse the explicit deployment allowlist without accepting arbitrary IDs."""
    if raw.strip() == "[]":
        return ()
    values = tuple(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))
    if any(len(item) > 63 or not _valid_project_id(item) for item in values):
        raise ValueError("experience project catalog contains an invalid project identifier")
    return values


def opaque_project_handle(project_id: str) -> str:
    """Return a stable navigation handle that does not contain the project ID."""
    return "project-h-" + hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:40]


def catalog_revision(project_ids: tuple[str, ...]) -> str:
    """Return a stable revision for the server-owned visible-project set."""
    return "catalog-r-" + hashlib.sha256("\n".join(project_ids).encode("utf-8")).hexdigest()[:40]


def selection_revision(handle: str, catalog_rev: str) -> str:
    """Return a non-sensitive revision for one server-side selection."""
    return "selection-r-" + hashlib.sha256(f"{handle}|{catalog_rev}".encode()).hexdigest()[:40]


def _valid_project_id(value: str) -> bool:
    return (
        bool(value)
        and value[0].islower()
        and all(char.islower() or char.isdigit() or char == "-" for char in value)
    )
