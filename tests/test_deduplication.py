"""Tests for deduplication and cross-sensor concordance tagging."""

from app.schemas.hotspot import HotspotObservation
from app.utils.deduplication import deduplicate_observations


def build(
    observation_id: str,
    sensor: str,
    satellite: str,
    lat: float,
    lon: float,
    date: str,
    time: str,
    confidence_level: str = "high",
) -> HotspotObservation:
    acquired_at = f"{date}T{time[:2]}:{time[2:4]}:00+00:00"
    return HotspotObservation(
        id=observation_id,
        observation_id=observation_id,
        latitude=lat,
        longitude=lon,
        acquired_at=acquired_at,
        observed_at_utc=acquired_at,
        acq_date=date,
        acq_time=time,
        sensor=sensor,
        satellite=satellite,
        instrument=sensor,
        confidence_raw="h" if sensor == "VIIRS" else 85,
        confidence_level=confidence_level,
        confidence_score=90,
        department="Antioquia",
        municipality="Caucasia",
        source="test",
        source_origin="NASA_FIRMS",
    )


def test_exact_duplicates_removed() -> None:
    first = build("A", "VIIRS", "NOAA-20", 7.985, -75.195, "2026-11-10", "1258")
    duplicate = build("A", "VIIRS", "NOAA-20", 7.985, -75.195, "2026-11-10", "1258")
    result = deduplicate_observations([first, duplicate])
    assert len(result) == 1
    assert result[0].observation_id == "A"


def test_cross_sensor_concordance_tagged() -> None:
    viirs = build("V1", "VIIRS", "NOAA-20", 7.985, -75.195, "2026-11-10", "1258")
    modis = build("M1", "MODIS", "Terra", 7.990, -75.190, "2026-11-10", "1300")
    result = deduplicate_observations([viirs, modis])
    assert len(result) == 2
    assert result[0].concordance == "coincident_high"
    assert result[1].concordance == "coincident_high"


def test_concordance_moderate_when_no_high_confidence() -> None:
    viirs = build(
        "V1",
        "VIIRS",
        "NOAA-20",
        7.985,
        -75.195,
        "2026-11-10",
        "1258",
        confidence_level="nominal",
    )
    modis = build(
        "M1",
        "MODIS",
        "Terra",
        7.990,
        -75.190,
        "2026-11-10",
        "1300",
        confidence_level="nominal",
    )
    result = deduplicate_observations([viirs, modis])
    assert result[0].concordance == "coincident_moderate"


def test_far_or_late_pairs_not_tagged() -> None:
    far = [
        build("V1", "VIIRS", "NOAA-20", 7.985, -75.195, "2026-11-10", "1258"),
        build("M1", "MODIS", "Terra", 8.500, -75.195, "2026-11-10", "1258"),
    ]
    result = deduplicate_observations(far)
    assert all(observation.concordance == "single_sensor" for observation in result)

    late = [
        build("V2", "VIIRS", "NOAA-20", 7.985, -75.195, "2026-11-10", "1258"),
        build("M2", "MODIS", "Terra", 7.985, -75.195, "2026-11-10", "1800"),
    ]
    result = deduplicate_observations(late)
    assert all(observation.concordance == "single_sensor" for observation in result)


def test_result_sorted_newest_first() -> None:
    older = build("A", "VIIRS", "NOAA-20", 7.985, -75.195, "2026-11-08", "1258")
    newer = build("B", "VIIRS", "NOAA-20", 7.985, -75.195, "2026-11-10", "1258")
    result = deduplicate_observations([older, newer])
    assert [observation.observation_id for observation in result] == ["B", "A"]
