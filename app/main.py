"""FastAPI application for the NASA Fire Harmonization backend."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import API_VERSION
from app.api.routes import firms, fusion, health, ideam, observations, status

_DEFAULT_DEV_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
)


def _allowed_origins() -> list[str]:
    """Origins allowed by CORS, configured through ALLOWED_ORIGINS (comma separated)."""
    raw = os.environ.get("ALLOWED_ORIGINS", _DEFAULT_DEV_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


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
