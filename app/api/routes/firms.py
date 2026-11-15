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
    description=(
        "Fetches the three public FIRMS Earthdata CSV feeds in parallel "
        "(MODIS C6.1, VIIRS NOAA-20, VIIRS NOAA-21; last 7 days, no MAP_KEY "
        "required) and filters them to the requested region/bbox. Does not "
        "require a `from`/`to` range: the feeds always cover the last 7 "
        "days. Cached 15 minutes; `feedsLoaded` reports which feeds "
        "actually responded. During a total FIRMS outage the last stored "
        "snapshot for Colombia is served with `degradedMode: true`."
    ),
    response_model=FirmsResponse,
    response_model_exclude_none=True,
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
