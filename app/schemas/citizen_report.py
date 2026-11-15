"""Contracts for citizen-submitted fire reports."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ReportRole = Literal["con experiencia", "habitante o testigo"]
ReportStatus = Literal["pendiente", "verificado"]


class CitizenReportCreate(BaseModel):
    """Fields accepted when a person submits a report."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    sector: str | None = Field(default=None, max_length=160)
    intensity: str = Field(min_length=1, max_length=80)
    note: str = Field(min_length=5, max_length=4000)
    role: ReportRole
    experience: str | None = Field(default=None, max_length=500)
    name: str | None = Field(default=None, max_length=160)
    contact: str | None = Field(default=None, max_length=240)


class CitizenReport(CitizenReportCreate):
    """Persisted citizen report returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    status: ReportStatus


class CitizenReportCollection(BaseModel):
    """Paginated report listing."""

    reports: list[CitizenReport]
    count: int


class CitizenReportStatusUpdate(BaseModel):
    """Allowed moderation state transition."""

    status: ReportStatus
