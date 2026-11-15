"""Open-Meteo integration for contextual weather data."""

from datetime import UTC, datetime
from typing import Any

import httpx

from app.schemas.weather import WeatherContext, WeatherCurrent, WeatherDaily

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 8.0


class WeatherServiceError(Exception):
    """Raised when Open-Meteo cannot provide a valid response."""


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


async def fetch_weather(
    latitude: float,
    longitude: float,
    location_name: str,
    client: httpx.AsyncClient | None = None,
) -> WeatherContext:
    """Fetch and normalize current and recent daily weather values."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,relative_humidity_2m,precipitation,"
            "wind_speed_10m,wind_direction_10m"
        ),
        "daily": "precipitation_sum,temperature_2m_max",
        "past_days": 3,
        "forecast_days": 1,
        "timezone": "auto",
    }
    http = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    owns_client = client is None
    try:
        try:
            response = await http.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WeatherServiceError("No fue posible consultar Open-Meteo.") from exc

        current = payload.get("current", {})
        daily = payload.get("daily", {})
        dates = daily.get("time", [])
        precipitation = daily.get("precipitation_sum", [])
        temperatures = daily.get("temperature_2m_max", [])
        daily_recent = [
            WeatherDaily(
                date=date,
                precipitationSumMm=(
                    _number(precipitation[index]) if index < len(precipitation) else None
                ),
                tempMaxC=_number(temperatures[index]) if index < len(temperatures) else None,
            )
            for index, date in enumerate(dates)
            if isinstance(date, str)
        ]
        return WeatherContext(
            latitude=latitude,
            longitude=longitude,
            locationName=location_name,
            fetchedAt=datetime.now(UTC).isoformat(),
            timezone=str(payload.get("timezone", "auto")),
            current=WeatherCurrent(
                temperatureC=_number(current.get("temperature_2m")),
                relativeHumidityPct=_number(current.get("relative_humidity_2m")),
                precipitationMm=_number(current.get("precipitation")),
                windSpeedKmh=_number(current.get("wind_speed_10m")),
                windDirectionDeg=_number(current.get("wind_direction_10m")),
            ),
            dailyRecent=daily_recent,
            available=True,
            sourceName="Open-Meteo",
            note=(
                "Contexto ambiental complementario; no confirma incendios ni "
                "sustituye la observación satelital."
            ),
        )
    finally:
        if owns_client:
            await http.aclose()
