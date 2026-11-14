"""Pydantic response models for the real-data ingestion endpoints.

Field names and JSON aliases replicate the payloads of the reference
application (``server.ts`` of the Ejemplo project) so both frontends can
consume this API without changes.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.hotspot import HotspotObservation


def _aliased_config() -> ConfigDict:
    return ConfigDict(populate_by_name=True)


class BboxModel(BaseModel):
    """Effective bounding box applied to a query."""

    model_config = _aliased_config()

    west: float
    south: float
    east: float
    north: float


class IngestMetadata(BaseModel):
    """Provenance and coverage metadata of an ingestion payload."""

    model_config = _aliased_config()

    source: str
    fetched_at_utc: str = Field(serialization_alias="fetchedAtUtc")
    from_: str = Field(serialization_alias="from")
    to: str
    region: str
    bbox: BboxModel
    files_loaded: list[str] = Field(default_factory=list, serialization_alias="filesLoaded")
    raw_count: int = Field(serialization_alias="rawCount")
    deduplicated_count: int = Field(serialization_alias="deduplicatedCount")
    attribution: str
    ideam_raw_count: int | None = Field(default=None, serialization_alias="ideamRawCount")
    firms_raw_count: int | None = Field(default=None, serialization_alias="firmsRawCount")


class FusionResponse(BaseModel):
    """Response of the IDEAM, fusion and historical ingestion endpoints."""

    model_config = _aliased_config()

    ok: Literal[True] = True
    cached: bool = False
    degraded_mode: bool = Field(serialization_alias="degradedMode")
    warning: str | None = None
    metadata: IngestMetadata
    observations: list[HotspotObservation]


class FirmsResponse(BaseModel):
    """Response of the public NASA FIRMS endpoint."""

    model_config = _aliased_config()

    ok: Literal[True] = True
    public_nrt_mode: bool = Field(serialization_alias="publicNrtMode")
    has_map_key: bool = Field(serialization_alias="hasMapKey")
    source: str
    feeds_loaded: list[str] = Field(serialization_alias="feedsLoaded")
    bbox: BboxModel
    fetched_at_utc: str = Field(serialization_alias="fetchedAtUtc")
    count: int
    warning: str | None = None
    observations: list[HotspotObservation]


class IdeamDirectoryResponse(BaseModel):
    """Response of the IDEAM portal file index endpoint."""

    model_config = _aliased_config()

    ok: Literal[True] = True
    portal_url: str = Field(serialization_alias="portalUrl")
    total_files: int = Field(serialization_alias="totalFiles")
    latest_dates: list[str] = Field(serialization_alias="latestDates")


class ServiceStatus(BaseModel):
    """Response of the public service status endpoint (/api/health)."""

    model_config = _aliased_config()

    ok: Literal[True] = True
    service: str
    timestamp_utc: str = Field(serialization_alias="timestampUtc")
    has_firms_map_key: bool = Field(serialization_alias="hasFirmsMapKey")
    firms_public_nrt_available: bool = Field(serialization_alias="firmsPublicNrtAvailable")
    ideam_max_days_per_query: int = Field(serialization_alias="ideamMaxDaysPerQuery")


AnyIngestResponse = FusionResponse | FirmsResponse | IdeamDirectoryResponse | ServiceStatus


def payload_of(response: AnyIngestResponse) -> dict[str, Any]:
    """Serialize a response model to the JSON payload exposed by the API."""
    return response.model_dump(by_alias=True, mode="json")
