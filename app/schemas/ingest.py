"""Pydantic response models for the real-data ingestion endpoints.

Field names and JSON aliases replicate the payloads of the reference
application (``server.ts`` of the Ejemplo project) so both frontends can
consume this API without changes.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.hotspot import HotspotObservation


def _aliased_config(**extra: Any) -> ConfigDict:
    return ConfigDict(populate_by_name=True, **extra)


_EXAMPLE_OBSERVATION: dict = {
    "id": "IDEAM_VIIRS_202611131349_6.3764_-74.3615",
    "observation_id": "IDEAM_VIIRS_202611131349_6.3764_-74.3615",
    "latitude": 6.3764,
    "longitude": -74.3615,
    "acquired_at": "2026-11-13T18:49:00+00:00",
    "observedAtUtc": "2026-11-13T18:49:00+00:00",
    "observedAtLocalCot": "2026-11-13 13:49",
    "acq_date": "2026-11-13",
    "acq_time": "1349",
    "sensor": "VIIRS",
    "satellite": "NOAA-20",
    "instrument": "VIIRS",
    "confidence_raw": "Nominal",
    "confidence_level": "nominal",
    "confidence_score": 60,
    "frp_mw": 5.2,
    "daynight": "N",
    "concordance": "single_sensor",
    "department": "Antioquia",
    "municipality": "Puerto Berrío",
    "source": "IDEAM (VIIRS-NOAA-20)",
    "source_origin": "IDEAM",
    "is_synthetic": False,
}

_EXAMPLE_METADATA: dict = {
    "source": "IDEAM - SMByC Colombia",
    "fetchedAtUtc": "2026-11-14T19:23:00+00:00",
    "from": "2026-11-09",
    "to": "2026-11-13",
    "region": "antioquia_ideam",
    "bbox": {"west": -78.73352, "south": 5.04717, "east": -72.27356, "north": 9.24309},
    "filesLoaded": ["Puntos_de_calor_Colombia_2026-11-09.csv"],
    "rawCount": 639,
    "deduplicatedCount": 639,
    "attribution": (
        "IDEAM - SMByC. Puntos de calor en Colombia (https://puntosdecalor.ideam.gov.co/). "
        "Fuente original: NASA LANCE FIRMS."
    ),
}


class BboxModel(BaseModel):
    """Effective bounding box applied to a query."""

    model_config = _aliased_config()

    west: float
    south: float
    east: float
    north: float


class IngestMetadata(BaseModel):
    """Provenance and coverage metadata of an ingestion payload."""

    model_config = _aliased_config(json_schema_extra={"example": _EXAMPLE_METADATA})

    source: str
    fetched_at_utc: str = Field(alias="fetchedAtUtc")
    from_: str = Field(alias="from")
    to: str
    region: str
    bbox: BboxModel
    files_loaded: list[str] = Field(default_factory=list, alias="filesLoaded")
    raw_count: int = Field(alias="rawCount")
    deduplicated_count: int = Field(alias="deduplicatedCount")
    attribution: str
    ideam_raw_count: int | None = Field(default=None, alias="ideamRawCount")
    firms_raw_count: int | None = Field(default=None, alias="firmsRawCount")


class FusionResponse(BaseModel):
    """Response of the IDEAM and fusion ingestion endpoints."""

    model_config = _aliased_config(
        json_schema_extra={
            "example": {
                "ok": True,
                "cached": False,
                "degradedMode": False,
                "warning": None,
                "metadata": _EXAMPLE_METADATA,
                "observations": [_EXAMPLE_OBSERVATION],
            }
        }
    )

    ok: Literal[True] = True
    cached: bool = False
    degraded_mode: bool = Field(alias="degradedMode")
    warning: str | None = None
    metadata: IngestMetadata
    observations: list[HotspotObservation]


class FirmsResponse(BaseModel):
    """Response of the public NASA FIRMS endpoint."""

    model_config = _aliased_config(
        json_schema_extra={
            "example": {
                "ok": True,
                "publicNrtMode": True,
                "hasMapKey": False,
                "source": (
                    "NASA FIRMS Earthdata Public NRT 7d "
                    "(MODIS C6.1 + VIIRS NOAA-20 + VIIRS NOAA-21)"
                ),
                "feedsLoaded": ["MODIS_C6_1_7d", "VIIRS_NOAA20_7d", "VIIRS_NOAA21_7d"],
                "bbox": {"west": -79.2, "south": -4.3, "east": -66.8, "north": 12.6},
                "fetchedAtUtc": "2026-11-14T19:24:00+00:00",
                "count": 3731,
                "warning": (
                    "Usando feeds CSV públicos oficiales NASA FIRMS 7d (Sudamérica) "
                    "filtrados a Colombia/Antioquia."
                ),
                "observations": [_EXAMPLE_OBSERVATION],
            }
        }
    )

    ok: Literal[True] = True
    degraded_mode: bool | None = Field(default=None, alias="degradedMode")
    public_nrt_mode: bool = Field(alias="publicNrtMode")
    has_map_key: bool = Field(alias="hasMapKey")
    source: str
    feeds_loaded: list[str] = Field(alias="feedsLoaded")
    bbox: BboxModel
    fetched_at_utc: str = Field(alias="fetchedAtUtc")
    count: int
    warning: str | None = None
    observations: list[HotspotObservation]


class IdeamDirectoryResponse(BaseModel):
    """Response of the IDEAM portal file index endpoint."""

    model_config = _aliased_config(
        json_schema_extra={
            "example": {
                "ok": True,
                "portalUrl": "https://puntosdecalor.ideam.gov.co/archivos-csv/",
                "totalFiles": 1048,
                "latestDates": ["2026-11-14", "2026-11-13", "2026-11-12"],
            }
        }
    )

    ok: Literal[True] = True
    portal_url: str = Field(alias="portalUrl")
    total_files: int = Field(alias="totalFiles")
    latest_dates: list[str] = Field(alias="latestDates")


class ServiceStatus(BaseModel):
    """Response of the public service status endpoint (/api/health)."""

    model_config = _aliased_config(
        json_schema_extra={
            "example": {
                "ok": True,
                "service": "NASA Fire Harmonization API - Public Data Ingest",
                "timestampUtc": "2026-11-14T19:25:25.550672+00:00",
                "hasGeminiKey": False,
                "hasFirmsKey": False,
                "firmsPublicNrtAvailable": True,
                "ideamMaxDaysPerQuery": 90,
                "citizenReportsCount": 0,
            }
        }
    )

    ok: Literal[True] = True
    service: str
    timestamp_utc: str = Field(alias="timestampUtc")
    has_gemini_key: bool = Field(alias="hasGeminiKey", default=False)
    has_firms_key: bool = Field(alias="hasFirmsKey", default=False)
    firms_public_nrt_available: bool = Field(alias="firmsPublicNrtAvailable", default=True)
    ideam_max_days_per_query: int = Field(alias="ideamMaxDaysPerQuery")
    citizen_reports_count: int = Field(alias="citizenReportsCount", default=0)


AnyIngestResponse = FusionResponse | FirmsResponse | IdeamDirectoryResponse | ServiceStatus


class ReadinessStatus(BaseModel):
    """Response of the /healthz readiness probe (no /api prefix)."""

    model_config = ConfigDict(populate_by_name=True)

    ok: Literal[True] = True
    service: str
    uptime_sec: int = Field(alias="uptimeSec")


def payload_of(response: AnyIngestResponse) -> dict[str, Any]:
    """Serialize a response model to the JSON payload exposed by the API."""
    return response.model_dump(by_alias=True, mode="json")
