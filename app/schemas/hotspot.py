"""Pydantic models for the real-data ingestion contract (Ejemplo-shaped).

The field names and JSON keys replicate the ``FireObservation`` contract of
the reference application so both frontends can consume this API without
changes. Two keys are camelCase there (``observedAtUtc`` and
``observedAtLocalCot``); they are exposed through serialization aliases.

Domain rules preserved from this repository:
- ``confidence_raw`` keeps the original value of the source product without
  reinterpretation.
- ``confidence_level`` / ``confidence_score`` are a provisional display
  heuristic replicated from the reference application; they are NOT the
  approved scientific normalization pending with Science/Data (ROADMAP F4).
- Every record carries provenance fields; ``is_synthetic`` is False only for
  real observations ingested from their official sources.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SensorType = Literal["MODIS", "VIIRS", "GROUND", "UNKNOWN"]
ConfidenceLevel = Literal["low", "nominal", "high"]
DayNight = Literal["D", "N"]
ConcordanceType = Literal["single_sensor", "coincident_high", "coincident_moderate"]
DataSourceOrigin = Literal["IDEAM", "NASA_FIRMS", "CITIZEN", "SYNTHETIC"]
VerificationStatus = Literal["verified", "pending"]


class HotspotObservation(BaseModel):
    """A single thermal detection as exposed by the ingestion endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    observation_id: str
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    acquired_at: str = Field(description="Acquisition instant as ISO 8601 UTC string.")
    observed_at_utc: str | None = Field(default=None, serialization_alias="observedAtUtc")
    observed_at_local_cot: str | None = Field(
        default=None, serialization_alias="observedAtLocalCot"
    )
    acq_date: str = Field(description="UTC date used for daily grouping (YYYY-MM-DD).")
    acq_time: str = Field(description="UTC acquisition time (HHMM).")
    sensor: SensorType
    satellite: str
    instrument: str
    confidence_raw: str | int | None
    confidence_level: ConfidenceLevel
    confidence_score: float
    frp_mw: float | None = None
    brightness_k: float | None = None
    secondary_brightness_k: float | None = None
    scan_km: float | None = None
    track_km: float | None = None
    daynight: DayNight | None = None
    concordance: ConcordanceType = "single_sensor"
    department: str
    municipality: str
    source: str
    source_origin: DataSourceOrigin
    verification_status: VerificationStatus | None = None
    quality_flags: list[str] = Field(default_factory=list)
    ingested_at: str | None = None
    reference_url: str | None = None
    is_synthetic: bool = False
