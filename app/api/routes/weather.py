"""HTTP route for contextual Open-Meteo weather data."""

from fastapi import APIRouter, HTTPException, Query

from app.schemas.weather import WeatherContext
from app.services.weather_service import WeatherServiceError, fetch_weather

router = APIRouter(prefix="/api", tags=["weather"])


@router.get(
    "/weather",
    response_model=WeatherContext,
    summary="Get contextual weather for a map location.",
)
async def get_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    name: str = Query("Ubicación seleccionada", min_length=1, max_length=120),
) -> WeatherContext:
    try:
        return await fetch_weather(lat, lon, name)
    except WeatherServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
