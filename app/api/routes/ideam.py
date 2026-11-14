"""HTTP routes for the real IDEAM ingestion endpoints.

Routes stay thin: they validate/normalize parameters, delegate to the
ingest service, and translate service failures into the documented error
payload ``{"ok": false, "error": "..."}`` used by the reference frontend.
"""

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.api.routes.route_helpers import (
    default_date_window,
    ingestion_error_response,
)
from app.schemas.ingest import FusionResponse, IdeamDirectoryResponse
from app.services import ingest_service

router = APIRouter(prefix="/api/ideam", tags=["ingestion"])


@router.get(
    "/directory",
    summary="List the daily IDEAM CSV files currently published by the portal.",
    response_model=IdeamDirectoryResponse,
)
async def get_directory() -> IdeamDirectoryResponse | JSONResponse:
    """Return the dates of the daily files available on the IDEAM portal."""
    try:
        return await ingest_service.get_ideam_directory()
    except Exception as error:
        return ingestion_error_response(error, "Error consultando índice IDEAM")


@router.get(
    "/observations",
    summary="Real thermal observations from the official IDEAM daily CSVs.",
    response_model=FusionResponse,
)
async def get_observations(
    from_: Annotated[
        str | None, Query(alias="from", description="Start date (YYYY-MM-DD, inclusive).")
    ] = None,
    to: Annotated[str | None, Query(description="End date (YYYY-MM-DD, inclusive).")] = None,
    region: Annotated[
        str,
        Query(description="Region alias: antioquia | antioquia_ideam | colombia | colombia_wide."),
    ] = "antioquia",
    bbox: Annotated[
        str | None,
        Query(description="Explicit bbox: 'west,south,east,north' or IDEAM extent form."),
    ] = None,
) -> FusionResponse | JSONResponse:
    """Return real IDEAM observations for the requested window and region."""
    try:
        from_date, to_date = default_date_window(days=44, to_date=to)
        if from_ is not None:
            from_date = from_
        return await ingest_service.get_ideam_observations(from_date, to_date, region, bbox)
    except ValueError as error:
        return ingestion_error_response(error, str(error), status_code=400)
    except Exception as error:
        message = str(error) or "Error al obtener observaciones reales del IDEAM"
        return ingestion_error_response(error, message)
