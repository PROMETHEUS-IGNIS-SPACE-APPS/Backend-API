"""HTTP routes for citizen reports."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.repositories import citizen_report_repository
from app.schemas.citizen_report import (
    CitizenReport,
    CitizenReportCollection,
    CitizenReportCreate,
    CitizenReportStatusUpdate,
)

router = APIRouter(prefix="/api", tags=["citizen-reports"])


@router.post(
    "/citizen-reports",
    response_model=CitizenReport,
    status_code=status.HTTP_201_CREATED,
    summary="Create a citizen fire report.",
)
def create_citizen_report(payload: CitizenReportCreate) -> CitizenReport:
    return citizen_report_repository.create_report(payload)


@router.get(
    "/citizen-reports",
    response_model=CitizenReportCollection,
    summary="List recent citizen fire reports.",
)
def get_citizen_reports(
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> CitizenReportCollection:
    reports = citizen_report_repository.list_reports(limit)
    return CitizenReportCollection(reports=reports, count=len(reports))


@router.patch(
    "/citizen-reports/{report_id}",
    response_model=CitizenReport,
    summary="Update a citizen report moderation status.",
)
def patch_citizen_report(
    report_id: UUID, payload: CitizenReportStatusUpdate
) -> CitizenReport:
    report = citizen_report_repository.update_status(report_id, payload.status)
    if report is None:
        raise HTTPException(status_code=404, detail="Reporte ciudadano no encontrado.")
    return report


@router.delete(
    "/citizen-reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a citizen report.",
)
def remove_citizen_report(report_id: UUID) -> None:
    if not citizen_report_repository.delete_report(report_id):
        raise HTTPException(status_code=404, detail="Reporte ciudadano no encontrado.")
