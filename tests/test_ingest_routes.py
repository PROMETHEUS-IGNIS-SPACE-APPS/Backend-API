"""Tests for the real-data ingestion HTTP endpoints (network mocked out)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.hotspot import HotspotObservation
from app.schemas.ingest import (
    BboxModel,
    FirmsResponse,
    FusionResponse,
    IdeamDirectoryResponse,
    IngestMetadata,
)
from app.services import ingest_service

client = TestClient(app)


def build_observation() -> HotspotObservation:
    return HotspotObservation(
        id="IDEAM_MODIS_202611100658_7.9850_-75.1950",
        observation_id="IDEAM_MODIS_202611100658_7.9850_-75.1950",
        latitude=7.985,
        longitude=-75.195,
        acquired_at="2026-11-10T11:58:00+00:00",
        observed_at_utc="2026-11-10T11:58:00+00:00",
        observed_at_local_cot="2026-11-10 06:58",
        acq_date="2026-11-10",
        acq_time="0658",
        sensor="MODIS",
        satellite="Terra",
        instrument="MODIS",
        confidence_raw="80",
        confidence_level="high",
        confidence_score=80,
        frp_mw=12.5,
        department="Antioquia",
        municipality="Caucasia",
        source="IDEAM (MODIS-Terra)",
        source_origin="IDEAM",
    )


def build_fusion_metadata() -> IngestMetadata:
    return IngestMetadata(
        source="IDEAM - SMByC Colombia",
        fetched_at_utc="2026-11-14T00:00:00+00:00",
        from_="2026-10-01",
        to="2026-11-10",
        region="antioquia",
        bbox=BboxModel(west=-77.35, south=5.4, east=-73.85, north=8.95),
        files_loaded=["Puntos_de_calor_Colombia_2026-11-10.csv"],
        raw_count=1,
        deduplicated_count=1,
        attribution="test attribution",
    )


def build_fusion_response() -> FusionResponse:
    return FusionResponse(
        degraded_mode=False,
        warning=None,
        metadata=build_fusion_metadata(),
        observations=[build_observation()],
    )


def build_firms_response() -> FirmsResponse:
    return FirmsResponse(
        public_nrt_mode=True,
        has_map_key=False,
        source="NASA FIRMS Earthdata Public NRT 7d",
        feeds_loaded=["MODIS_C6_1_7d"],
        bbox=BboxModel(west=-79.2, south=-4.3, east=-66.8, north=12.6),
        fetched_at_utc="2026-11-14T00:00:00+00:00",
        count=1,
        warning=None,
        observations=[build_observation()],
    )


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch):
    """Allow each test to install fake service functions."""

    def _patch(**functions):
        for name, function in functions.items():
            monkeypatch.setattr(ingest_service, name, function)

    return _patch


# --- GET /api/ideam/observations ---


def test_ideam_observations_happy_path(patched) -> None:
    async def fake(
        from_date: str, to_date: str, region: str, bbox_param: str | None
    ) -> FusionResponse:
        assert from_date == "2026-10-01"
        assert to_date == "2026-11-10"
        return build_fusion_response()

    patched(get_ideam_observations=fake)

    response = client.get(
        "/api/ideam/observations", params={"from": "2026-10-01", "to": "2026-11-10"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["degradedMode"] is False
    assert body["metadata"]["from"] == "2026-10-01"
    assert body["metadata"]["filesLoaded"] == ["Puntos_de_calor_Colombia_2026-11-10.csv"]
    observation = body["observations"][0]
    assert observation["observation_id"].startswith("IDEAM_")
    assert observation["observedAtUtc"] == "2026-11-10T11:58:00+00:00"
    assert observation["observedAtLocalCot"] == "2026-11-10 06:58"
    assert observation["confidence_raw"] == "80"


def test_ideam_observations_invalid_range_returns_400(patched) -> None:
    async def fake(from_date, to_date, region, bbox_param):
        raise ValueError("Rango de fechas inválido")

    patched(get_ideam_observations=fake)

    response = client.get("/api/ideam/observations", params={"from": "bad", "to": "bad"})

    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_ideam_observations_upstream_failure_returns_502(patched) -> None:
    async def fake(from_date, to_date, region, bbox_param):
        raise RuntimeError("No fue posible descargar archivos CSV del IDEAM (x.csv)")

    patched(get_ideam_observations=fake)

    response = client.get("/api/ideam/observations")

    assert response.status_code == 502
    body = response.json()
    assert body["ok"] is False
    assert "No fue posible" in body["error"]


# --- GET /api/ideam/directory ---


def test_ideam_directory_happy_path(patched) -> None:
    async def fake() -> IdeamDirectoryResponse:
        return IdeamDirectoryResponse(
            portal_url="https://puntosdecalor.ideam.gov.co/archivos-csv/",
            total_files=1,
            latest_dates=["2026-11-13"],
        )

    patched(get_ideam_directory=fake)

    response = client.get("/api/ideam/directory")

    assert response.status_code == 200
    body = response.json()
    assert body["totalFiles"] == 1
    assert body["latestDates"] == ["2026-11-13"]


def test_ideam_directory_failure_returns_502(patched) -> None:
    async def fake() -> IdeamDirectoryResponse:
        raise RuntimeError("IDEAM HTTP 500")

    patched(get_ideam_directory=fake)

    response = client.get("/api/ideam/directory")

    assert response.status_code == 502


# --- GET /api/firms/observations ---


def test_firms_observations_happy_path(patched) -> None:
    async def fake(region: str, bbox_param: str | None) -> FirmsResponse:
        assert region == "colombia"
        return build_firms_response()

    patched(get_firms_observations=fake)

    response = client.get("/api/firms/observations")

    assert response.status_code == 200
    body = response.json()
    assert body["publicNrtMode"] is True
    assert body["hasMapKey"] is False
    assert body["feedsLoaded"] == ["MODIS_C6_1_7d"]
    assert body["count"] == 1


def test_firms_observations_failure_returns_502(patched) -> None:
    async def fake(region: str, bbox_param: str | None) -> FirmsResponse:
        raise RuntimeError("Sin respuesta de feeds FIRMS")

    patched(get_firms_observations=fake)

    response = client.get("/api/firms/observations")

    assert response.status_code == 502
    assert response.json()["ok"] is False


# --- GET /api/fusion/observations ---


def test_fusion_observations_happy_path(patched) -> None:
    async def fake(from_date, to_date, region, bbox_param) -> FusionResponse:
        assert region == "colombia"
        return build_fusion_response()

    patched(get_fusion_observations=fake)

    response = client.get("/api/fusion/observations")

    assert response.status_code == 200
    assert response.json()["metadata"]["source"].startswith("IDEAM")


# --- GET /api/health ---


def test_public_health_reports_capabilities() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["hasFirmsKey"] is False
    assert body["hasGeminiKey"] is False
    assert body["firmsPublicNrtAvailable"] is True
    assert body["ideamMaxDaysPerQuery"] == 90
    assert body["citizenReportsCount"] == 0


# --- GET /healthz ---


def test_healthz_readiness_probe() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "prometheus-ignis"
    assert isinstance(body["uptimeSec"], int)
    assert body["uptimeSec"] >= 0


def test_ingestion_paths_documented_in_openapi() -> None:
    schema = client.get("/openapi.json").json()
    for path in (
        "/healthz",
        "/api/ideam/directory",
        "/api/ideam/observations",
        "/api/firms/observations",
        "/api/fusion/observations",
        "/api/health",
    ):
        assert path in schema["paths"]
    assert "/api/fusion/historical-all" not in schema["paths"]
