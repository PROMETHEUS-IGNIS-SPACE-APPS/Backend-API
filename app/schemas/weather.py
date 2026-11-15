"""Schemas for the Open-Meteo context endpoint."""

from pydantic import BaseModel, ConfigDict, Field


class WeatherCurrent(BaseModel):
    """Current weather values relevant to fire-risk interpretation."""

    temperature_c: float | None = Field(default=None, alias="temperatureC")
    relative_humidity_pct: float | None = Field(default=None, alias="relativeHumidityPct")
    precipitation_mm: float | None = Field(default=None, alias="precipitationMm")
    wind_speed_kmh: float | None = Field(default=None, alias="windSpeedKmh")
    wind_direction_deg: float | None = Field(default=None, alias="windDirectionDeg")

    model_config = ConfigDict(populate_by_name=True)


class WeatherDaily(BaseModel):
    """Recent daily precipitation and temperature summary."""

    date: str
    precipitation_sum_mm: float | None = Field(default=None, alias="precipitationSumMm")
    temp_max_c: float | None = Field(default=None, alias="tempMaxC")

    model_config = ConfigDict(populate_by_name=True)


class WeatherContext(BaseModel):
    """Normalized Open-Meteo response consumed by the Frontend."""

    latitude: float
    longitude: float
    location_name: str = Field(alias="locationName")
    fetched_at: str = Field(alias="fetchedAt")
    timezone: str
    current: WeatherCurrent
    daily_recent: list[WeatherDaily] = Field(default_factory=list, alias="dailyRecent")
    available: bool
    source_name: str = Field(alias="sourceName")
    note: str

    model_config = ConfigDict(populate_by_name=True)
