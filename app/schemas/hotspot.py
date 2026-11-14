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

_EXAMPLE_REFERENCE_URL = (
    "https://puntosdecalor.ideam.gov.co/archivos-csv/Puntos_de_calor_Colombia_2026-11-13.csv"
)

# Real record ingested live from the IDEAM portal on 2026-11-14; kept in
# sync with the documented contract example in docs/api-contracts.md.
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
    "brightness_k": 309.25,
    "secondary_brightness_k": 289.35,
    "scan_km": 0.55,
    "track_km": 0.51,
    "daynight": "N",
    "concordance": "single_sensor",
    "department": "Antioquia",
    "municipality": "Puerto Berrío",
    "source": "IDEAM (VIIRS-NOAA-20)",
    "source_origin": "IDEAM",
    "verification_status": None,
    "quality_flags": [],
    "ingested_at": "2026-11-14T19:23:00+00:00",
    "reference_url": _EXAMPLE_REFERENCE_URL,
    "is_synthetic": False,
}


class HotspotObservation(BaseModel):
    """A single thermal detection as exposed by the ingestion endpoints."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": _EXAMPLE_OBSERVATION},
    )
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
