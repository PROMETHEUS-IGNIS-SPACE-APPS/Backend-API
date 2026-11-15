"""HTTP routes for the multi-agency fusion and historical coverage endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.api.routes.route_helpers import (
    default_date_window,
    ingestion_error_response,
)
from app.schemas.ingest import FusionResponse
from app.services import ingest_service

router = APIRouter(prefix="/api/fusion", tags=["ingestion"])


@router.get(
    "/observations",
    summary="Fused IDEAM + NASA FIRMS observations for an inclusive date range.",
    description=(
        "Deduplicated merge of the official IDEAM daily CSVs and the NASA "
        "FIRMS public NRT 7d feeds for the requested window and region. "
        "Cross-sensor pairs of the same thermal anomaly (~1.6 km, ±90 min) "
        "are tagged through `concordance` instead of being silently "
        "overcounted. Results are cached 15 minutes."
    ),
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
    ] = "colombia",
    bbox: Annotated[
        str | None,
        Query(description="Explicit bbox: 'west,south,east,north' or IDEAM extent form."),
    ] = None,
) -> FusionResponse | JSONResponse:
    """Return fused multi-agency observations for the requested window."""
    try:
        from_date, to_date = default_date_window(days=44, to_date=to)
        if from_ is not None:
            from_date = from_
        return await ingest_service.get_fusion_observations(from_date, to_date, region, bbox)
    except Exception as error:
        message = str(error) or "Error en fusión multibase de datos"
        return ingestion_error_response(error, message)


@router.get(
    "/historical-all",
    summary=(
        "Multi-year coverage 2024-01-01 to today: sampled archive cuts, "
        "a dense recent window and live FIRMS."
    ),
    description=(
        "**Heavy endpoint**: builds the full multi-year coverage (dense last "
        "45 days + one IDEAM archive cut per half-month + live FIRMS), "
        "condensed to the 9000 most recent records to protect browser "
        "performance. First uncached call can take tens of seconds because "
        "it downloads up to ~110 daily files; afterwards it is served from "
        "a 30-minute cache (`cached: true`). Prefer `/api/fusion/observations` "
        "for interactive exploration."
    ),
    response_model=FusionResponse,
)
async def get_historical_all(
    region: Annotated[
        str,
        Query(description="Region alias: antioquia | antioquia_ideam | colombia | colombia_wide."),
    ] = "antioquia_ideam",
    bbox: Annotated[
        str | None,
        Query(description="Explicit bbox: 'west,south,east,north' or IDEAM extent form."),
    ] = None,
) -> FusionResponse | JSONResponse:
    """Return the condensed multi-year historical coverage."""
    try:
        return await ingest_service.get_historical_all(region, bbox)
    except Exception as error:
        message = str(error) or "Error consultando el histórico multi-anual disponible."
        return ingestion_error_response(error, message)
