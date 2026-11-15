"""HTTP routes for the public service status and capabilities probe."""

from fastapi import APIRouter

from app.schemas.ingest import ServiceStatus
from app.services.ingest_service import get_service_status

router = APIRouter(prefix="/api", tags=["status"])


@router.get(
    "/health",
    summary="Check that the service is running and report its ingestion capabilities.",
    description=(
        "Lightweight readiness probe with no remote calls. `hasFirmsKey` "
        "and `hasGeminiKey` are false because this deployment uses the "
        "public NRT feeds only and does not integrate AI assistance; "
        "`citizenReportsCount` is 0 while the citizen-report store is not "
        "part of this backend; `ideamMaxDaysPerQuery` states the hard "
        "limit enforced by the IDEAM endpoints."
    ),
    response_model=ServiceStatus,
)
def get_public_health() -> ServiceStatus:
    """Return the public status body with capability flags."""
    return get_service_status()
