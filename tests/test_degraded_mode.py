"""Tests for the degraded-mode snapshot fallback of the ingestion service.

No network access happens here: the IDEAM/FIRMS repositories are replaced
with fakes, and ``ingest_service.SNAPSHOT_DIR`` is redirected to a pytest
temporary directory so the real ``data/cache/`` folder is never touched.

The service-level fallback functions (``_run_ideam_window``,
``_run_firms_public``, ``_run_fusion``) are called directly to isolate the
fallback logic from the TTL cache; one route-level test covers the full
HTTP path through the cache.
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.firms_repository import FirmsFeedsResult
from app.repositories.ideam_repository import IdeamWindowResult
from app.schemas.hotspot import HotspotObservation
from app.schemas.ingest import BboxModel, FirmsResponse, FusionResponse, IngestMetadata
from app.services import ingest_service
from app.utils.geo import resolve_region_bbox

client = TestClient(app)

BBOX = resolve_region_bbox("antioquia")


@pytest.fixture(autouse=True)
def isolated_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Isolate each test: private caches cleared, snapshots in tmp_path."""
    monkeypatch.setattr(ingest_service, "SNAPSHOT_DIR", tmp_path)
    ingest_service._response_cache.clear()
    ingest_service._inflight_tasks.clear()
    yield
    ingest_service._response_cache.clear()
    ingest_service._inflight_tasks.clear()


# --- Builders and fakes (mirrors of the verified live payloads) ---


def build_observation() -> HotspotObservation:
    return HotspotObservation(
        id="IDEAM_VIIRS_202611131349_6.3764_-74.3615",
        observation_id="IDEAM_VIIRS_202611131349_6.3764_-74.3615",
        latitude=6.3764,
        longitude=-74.3615,
        acquired_at="2026-11-13T18:49:00+00:00",
        observed_at_utc="2026-11-13T18:49:00+00:00",
        observed_at_local_cot="2026-11-13 13:49",
        acq_date="2026-11-13",
        acq_time="1349",
        sensor="VIIRS",
        satellite="NOAA-20",
        instrument="VIIRS",
        confidence_raw="Nominal",
        confidence_level="nominal",
        confidence_score=60,
        frp_mw=5.2,
        department="Antioquia",
        municipality="Puerto Berrío",
        source="IDEAM (VIIRS-NOAA-20)",
        source_origin="IDEAM",
    )


def build_metadata(from_date: str = "2026-10-01", to_date: str = "2026-11-10") -> IngestMetadata:
    return IngestMetadata(
        source="IDEAM - SMByC Colombia",
        fetched_at_utc="2026-11-14T19:23:00+00:00",
        from_=from_date,
        to=to_date,
        region="antioquia",
        bbox=BboxModel(**BBOX),
        files_loaded=["Puntos_de_calor_Colombia_2026-11-10.csv"],
        raw_count=1,
        deduplicated_count=1,
        attribution="test attribution",
    )


def build_fusion_response(
    from_date: str = "2026-10-01", to_date: str = "2026-11-10"
) -> FusionResponse:
    return FusionResponse(
        degraded_mode=False,
        warning=None,
        metadata=build_metadata(from_date, to_date),
        observations=[build_observation()],
    )


def build_firms_response() -> FirmsResponse:
    return FirmsResponse(
        public_nrt_mode=True,
        has_map_key=False,
        source="NASA FIRMS Earthdata Public NRT 7d",
        feeds_loaded=["MODIS_C6_1_7d"],
        bbox=BboxModel(west=-79.2, south=-4.3, east=-66.8, north=12.6),
        fetched_at_utc="2026-11-14T19:24:00+00:00",
        count=1,
        warning=None,
        observations=[build_observation()],
    )


class FakeIdeamRepository:
    """Stands in for ``ingest_service.ideam_repository``."""

    def __init__(
        self,
        observations: list[HotspotObservation] | None = None,
        loaded_files: list[str] | None = None,
        failed_files: list[str] | None = None,
    ) -> None:
        self.observations = observations or []
        self.loaded_files = loaded_files or []
        self.failed_files = failed_files or []

    async def fetch_window(self, from_date: str, to_date: str, bbox) -> IdeamWindowResult:
        return IdeamWindowResult(
            observations=self.observations,
            loaded_files=self.loaded_files,
            failed_files=self.failed_files,
            dates_count=len(self.loaded_files) + len(self.failed_files),
        )


class FakeFirmsRepository:
    """Stands in for ``ingest_service.firms_repository``."""

    def __init__(
        self,
        observations: list[HotspotObservation] | None = None,
        loaded_feeds: list[str] | None = None,
        failed_feeds: list[str] | None = None,
    ) -> None:
        self.observations = observations or []
        self.loaded_feeds = loaded_feeds or []
        self.failed_feeds = failed_feeds or []

    async def fetch_public_feeds(self, bbox) -> FirmsFeedsResult:
        return FirmsFeedsResult(
            observations=self.observations,
            loaded_feeds=self.loaded_feeds,
            failed_feeds=self.failed_feeds,
        )


# --- IDEAM window fallback ---


def test_ideam_window_serves_snapshot_when_all_files_fail(monkeypatch) -> None:
    stored = build_fusion_response()
    ingest_service._save_snapshot("last_ideam.json", stored)
    monkeypatch.setattr(
        ingest_service, "ideam_repository", FakeIdeamRepository(failed_files=["f1.csv", "f2.csv"])
    )

    result = asyncio.run(
        ingest_service._run_ideam_window("2026-11-09", "2026-11-13", "antioquia", BBOX)
    )

    assert result.degraded_mode is True
    assert result.warning is not None
    assert "IDEAM" in result.warning and "auténtico" in result.warning
    assert result.metadata is stored.metadata or result.metadata == stored.metadata
    assert result.observations == stored.observations


def test_ideam_window_raises_without_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        ingest_service, "ideam_repository", FakeIdeamRepository(failed_files=["f1.csv", "f2.csv"])
    )

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(ingest_service._run_ideam_window("2026-11-09", "2026-11-13", "antioquia", BBOX))

    message = str(excinfo.value)
    assert "No fue posible" in message
    assert "f1.csv" in message and "f2.csv" in message


def test_degraded_keeps_original_snapshot_dates(monkeypatch) -> None:
    stored = build_fusion_response(from_date="2026-10-01", to_date="2026-11-10")
    ingest_service._save_snapshot("last_ideam.json", stored)
    monkeypatch.setattr(
        ingest_service, "ideam_repository", FakeIdeamRepository(failed_files=["f1.csv"])
    )

    result = asyncio.run(
        ingest_service._run_ideam_window("2026-11-09", "2026-11-13", "antioquia", BBOX)
    )

    payload = result.model_dump(by_alias=True)
    # The degraded payload keeps the ORIGINAL stored window, not the new query.
    assert payload["metadata"]["from"] == "2026-10-01"
    assert payload["metadata"]["to"] == "2026-11-10"
    assert payload["metadata"]["filesLoaded"] == ["Puntos_de_calor_Colombia_2026-11-10.csv"]


# --- FIRMS feeds fallback ---


def test_firms_serves_snapshot_when_feeds_fail(monkeypatch) -> None:
    stored = build_firms_response()
    ingest_service._save_snapshot("last_firms.json", stored)
    monkeypatch.setattr(
        ingest_service,
        "firms_repository",
        FakeFirmsRepository(failed_feeds=["MODIS_C6_1_7d", "VIIRS_NOAA20_7d", "VIIRS_NOAA21_7d"]),
    )

    result = asyncio.run(ingest_service._run_firms_public(BBOX, "colombia"))

    assert result.ok is True
    assert result.degraded_mode is True
    assert result.public_nrt_mode is True
    assert result.feeds_loaded == stored.feeds_loaded
    assert result.observations == stored.observations
    assert result.warning is not None
    assert "NASA FIRMS" in result.warning and "snapshot" in result.warning


def test_firms_raises_without_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        ingest_service,
        "firms_repository",
        FakeFirmsRepository(failed_feeds=["MODIS_C6_1_7d"]),
    )

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(ingest_service._run_firms_public(BBOX, "colombia"))

    message = str(excinfo.value)
    assert "No fue posible acceder" in message
    assert "MODIS_C6_1_7d" in message


# --- Fusion fallback ---


def test_fusion_serves_snapshot_when_both_sources_fail(monkeypatch) -> None:
    stored = build_fusion_response()
    ingest_service._save_snapshot("last_fusion.json", stored)
    monkeypatch.setattr(
        ingest_service, "ideam_repository", FakeIdeamRepository(failed_files=["f.csv"])
    )
    monkeypatch.setattr(
        ingest_service, "firms_repository", FakeFirmsRepository(failed_feeds=["MODIS_C6_1_7d"])
    )

    result = asyncio.run(ingest_service._run_fusion("2026-11-09", "2026-11-13", "antioquia", BBOX))

    assert result.degraded_mode is True
    assert result.warning is not None
    assert "respaldo local" in result.warning
    assert result.metadata.raw_count == stored.metadata.raw_count


def test_fusion_raises_without_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        ingest_service, "ideam_repository", FakeIdeamRepository(failed_files=["f.csv"])
    )
    monkeypatch.setattr(
        ingest_service, "firms_repository", FakeFirmsRepository(failed_feeds=["MODIS_C6_1_7d"])
    )

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(ingest_service._run_fusion("2026-11-09", "2026-11-13", "antioquia", BBOX))

    assert "No se obtuvieron registros" in str(excinfo.value)


def test_fusion_partial_failure_flags_degraded(monkeypatch) -> None:
    # IDEAM returns nothing, FIRMS is alive: live FIRMS data, marked degraded.
    monkeypatch.setattr(
        ingest_service, "ideam_repository", FakeIdeamRepository(failed_files=["f.csv"])
    )
    monkeypatch.setattr(
        ingest_service,
        "firms_repository",
        FakeFirmsRepository(observations=[build_observation()], loaded_feeds=["MODIS_C6_1_7d"]),
    )

    result = asyncio.run(ingest_service._run_fusion("2026-11-09", "2026-11-13", "antioquia", BBOX))

    assert result.degraded_mode is True
    assert result.warning is not None
    assert "IDEAM no devolvió" in result.warning
    assert len(result.observations) == 1
    assert result.metadata.ideam_raw_count == 0
    assert result.metadata.firms_raw_count == 1


def test_fusion_success_persists_snapshot_only_for_degraded_region(monkeypatch) -> None:
    # antioquia_ideam is the only region whose fusion is snapshotted (Ejemplo behavior).
    monkeypatch.setattr(
        ingest_service,
        "ideam_repository",
        FakeIdeamRepository(observations=[build_observation()], loaded_files=["f.csv"]),
    )
    monkeypatch.setattr(
        ingest_service,
        "firms_repository",
        FakeFirmsRepository(observations=[build_observation()], loaded_feeds=["MODIS_C6_1_7d"]),
    )

    asyncio.run(ingest_service._run_fusion("2026-11-09", "2026-11-13", "antioquia_ideam", BBOX))
    assert (ingest_service.SNAPSHOT_DIR / "last_fusion.json").is_file()

    (ingest_service.SNAPSHOT_DIR / "last_fusion.json").unlink()
    asyncio.run(ingest_service._run_fusion("2026-11-09", "2026-11-13", "antioquia", BBOX))
    assert not (ingest_service.SNAPSHOT_DIR / "last_fusion.json").exists()


def test_ideam_success_persists_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        ingest_service,
        "ideam_repository",
        FakeIdeamRepository(observations=[build_observation()], loaded_files=["f.csv"]),
    )

    asyncio.run(ingest_service._run_ideam_window("2026-11-09", "2026-11-13", "antioquia", BBOX))

    assert (ingest_service.SNAPSHOT_DIR / "last_ideam.json").is_file()


def test_firms_success_persists_snapshot_only_for_colombia(monkeypatch) -> None:
    monkeypatch.setattr(
        ingest_service,
        "firms_repository",
        FakeFirmsRepository(observations=[build_observation()], loaded_feeds=["MODIS_C6_1_7d"]),
    )

    asyncio.run(ingest_service._run_firms_public(BBOX, "colombia"))
    assert (ingest_service.SNAPSHOT_DIR / "last_firms.json").is_file()

    (ingest_service.SNAPSHOT_DIR / "last_firms.json").unlink()
    asyncio.run(ingest_service._run_firms_public(BBOX, "antioquia"))
    assert not (ingest_service.SNAPSHOT_DIR / "last_firms.json").exists()


def test_fusion_ttl_cache_hit_marks_cached(monkeypatch) -> None:
    monkeypatch.setattr(
        ingest_service,
        "ideam_repository",
        FakeIdeamRepository(observations=[build_observation()], loaded_files=["f.csv"]),
    )
    monkeypatch.setattr(
        ingest_service,
        "firms_repository",
        FakeFirmsRepository(observations=[build_observation()], loaded_feeds=["MODIS_C6_1_7d"]),
    )

    fresh = asyncio.run(
        ingest_service.get_fusion_observations("2026-11-09", "2026-11-13", "antioquia", None)
    )
    assert fresh.cached is False

    hit = asyncio.run(
        ingest_service.get_fusion_observations("2026-11-09", "2026-11-13", "antioquia", None)
    )
    assert hit.cached is True


# --- Snapshot serialization ---


def test_snapshot_roundtrip_preserves_aliases() -> None:
    original = build_fusion_response()

    ingest_service._save_snapshot("roundtrip.json", original)
    loaded = ingest_service._load_fusion_snapshot("roundtrip.json")

    assert loaded is not None
    assert loaded.model_dump(by_alias=True) == original.model_dump(by_alias=True)
    assert loaded.observations[0].observed_at_utc == original.observations[0].observed_at_utc


def test_corrupt_snapshot_is_ignored_not_raised(monkeypatch) -> None:
    ingest_service.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    (ingest_service.SNAPSHOT_DIR / "last_fusion.json").write_text(
        "{not valid json", encoding="utf-8"
    )
    monkeypatch.setattr(
        ingest_service, "ideam_repository", FakeIdeamRepository(failed_files=["f.csv"])
    )
    monkeypatch.setattr(
        ingest_service, "firms_repository", FakeFirmsRepository(failed_feeds=["MODIS_C6_1_7d"])
    )

    with pytest.raises(RuntimeError):
        asyncio.run(ingest_service._run_fusion("2026-11-09", "2026-11-13", "antioquia", BBOX))


# --- Full HTTP path ---


def test_route_serves_degraded_ideam_payload(monkeypatch) -> None:
    stored = build_fusion_response()
    ingest_service._save_snapshot("last_ideam.json", stored)
    monkeypatch.setattr(
        ingest_service, "ideam_repository", FakeIdeamRepository(failed_files=["f1.csv"])
    )

    response = client.get(
        "/api/ideam/observations", params={"from": "2026-11-09", "to": "2026-11-10"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["degradedMode"] is True
    assert body["warning"] is not None
    assert body["metadata"]["from"] == "2026-10-01"
