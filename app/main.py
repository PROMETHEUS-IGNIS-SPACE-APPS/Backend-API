"""FastAPI application for the NASA Fire Harmonization backend."""

import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import API_VERSION
from app.api.routes import firms, fusion, health, ideam, observations, status
from app.schemas.ingest import ReadinessStatus

_STARTED_AT_MONOTONIC = time.monotonic()

_DEFAULT_DEV_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
)


def _allowed_origins() -> list[str]:
    """Origins allowed by CORS, configured through ALLOWED_ORIGINS (comma separated)."""
    raw = os.environ.get("ALLOWED_ORIGINS", _DEFAULT_DEV_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


_OPENAPI_TAGS = [
    {
        "name": "status",
        "description": (
            "Service availability and ingestion capabilities. Start here to "
            "check what this deployment can serve."
        ),
    },
    {
        "name": "ingestion",
        "description": (
            "Real data ingested live from official public sources (IDEAM-SMByC "
            "and NASA FIRMS public NRT). Responses carry full provenance and "
            "may degrade to an authentic stored snapshot during source "
            "outages (always announced via `degradedMode` + `warning`). "
            "Errors: 400 invalid dates, 502 sources unavailable."
        ),
    },
    {
        "name": "observations",
        "description": (
            "SYNTHETIC demo observations (contract v0.1). Data is labeled "
            '`data_provenance: "synthetic_demo"` and is NOT real NASA data.'
        ),
    },
    {
        "name": "health",
        "description": "Stable legacy health check for the v1 contract.",
    },
]


app = FastAPI(
    title="NASA Fire Harmonization API",
    version=API_VERSION,
    description=(
        "Backend for the NASA Space Apps Challenge 2026 challenge "
        "'Harmonization of MODIS and VIIRS Hot Spots'. "
        "The /api/v1 endpoints expose labeled synthetic demo data; the /api "
        "endpoints ingest real IDEAM and NASA FIRMS public data with their "
        "original provenance."
    ),
    openapi_tags=_OPENAPI_TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health.router)
app.include_router(observations.router)
app.include_router(status.router)
app.include_router(ideam.router)
app.include_router(firms.router)
app.include_router(fusion.router)


@app.get("/healthz", tags=["status"], summary="Readiness probe (no /api prefix).")
def readiness() -> ReadinessStatus:
    """Return the minimal readiness body, as the reference application does."""
    uptime = int(time.monotonic() - _STARTED_AT_MONOTONIC)
    return ReadinessStatus(service="prometheus-ignis", uptime_sec=uptime)
