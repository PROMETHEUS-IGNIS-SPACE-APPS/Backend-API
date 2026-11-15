from fastapi.testclient import TestClient

from app.api.routes import weather
from app.main import app
from app.schemas.weather import WeatherContext, WeatherCurrent

client = TestClient(app)


def test_weather_validates_coordinates() -> None:
    response = client.get("/api/weather?lat=91&lon=-75&name=Antioquia")

    assert response.status_code == 422


def test_weather_normalizes_open_meteo_context(monkeypatch) -> None:
    async def fake_fetch_weather(latitude: float, longitude: float, location_name: str):
        return WeatherContext(
            latitude=latitude,
            longitude=longitude,
            locationName=location_name,
            fetchedAt="2026-11-15T00:00:00+00:00",
            timezone="America/Bogota",
            current=WeatherCurrent(temperatureC=24, relativeHumidityPct=70),
            dailyRecent=[],
            available=True,
            sourceName="Open-Meteo",
            note="Contexto complementario.",
        )

    monkeypatch.setattr(weather, "fetch_weather", fake_fetch_weather)
    response = client.get("/api/weather?lat=6.4&lon=-75.6&name=Antioquia")

    assert response.status_code == 200
    assert response.json()["locationName"] == "Antioquia"
    assert response.json()["current"]["temperatureC"] == 24
