"""HTTP routes for the NASA FIRMS public NRT ingestion endpoint."""

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.api.routes.route_helpers import ingestion_error_response
from app.schemas.ingest import FirmsResponse
from app.services import ingest_service

router = APIRouter(prefix="/api/firms", tags=["ingestion"])


@router.get(
    "/observations",
    summary="Real observations from the public NASA FIRMS NRT 7d South America feeds.",
    response_model=FirmsResponse,
)
async def get_observations(
    region: Annotated[
        str,
        Query(description="Region alias: antioquia | antioquia_ideam | colombia | colombia_wide."),
    ] = "colombia",
    bbox: Annotated[
        str | None,
        Query(description="Explicit bbox: 'west,south,east,north' or IDEAM extent form."),
    ] = None,
) -> FirmsResponse | JSONResponse:
    """Return real FIRMS observations filtered to the requested region."""
    try:
        return await ingest_service.get_firms_observations(region, bbox)
    except Exception as error:
        message = str(error) or "Error consultando feeds públicos NASA FIRMS"
        return ingestion_error_response(error, message)
