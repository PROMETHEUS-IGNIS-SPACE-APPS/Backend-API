"""Tests for POST /api/ai/explain (Gemini is mocked; no network calls)."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ai_service

client = TestClient(app)

EXPLANATION = {
    "resumenEjecutivo": "Resumen.",
    "hallazgosClave": ["Hallazgo 1"],
    "interpretacionSensores": "VIIRS y MODIS se leen por separado.",
    "interpretacionMarkov": "BSS negativo: no supera la climatología.",
    "limitacionesYCautela": ["Un foco no es un incendio confirmado."],
    "recomendacionesOperativas": ["Verificar en terreno."],
}
BODY = {"mode": "predictability", "payload": {"p24": 0.31, "bss": -0.02}}


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    ai_service._cache.clear()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(ai_service, "load_env_file", lambda: None)


def _mock_gemini(monkeypatch: pytest.MonkeyPatch, status: int, body: dict) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):  # noqa: ANN002, ANN003
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", factory)
    monkeypatch.setattr(ai_service.asyncio, "sleep", lambda *_: _noop())
    return seen


async def _noop() -> None:
    return None


def test_explain_without_key_returns_503() -> None:
    response = client.post("/api/ai/explain", json=BODY)
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_explain_returns_structured_reading_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    gemini_body = {"candidates": [{"content": {"parts": [{"text": json.dumps(EXPLANATION)}]}}]}
    seen = _mock_gemini(monkeypatch, 200, gemini_body)

    first = client.post("/api/ai/explain", json=BODY)
    assert first.status_code == 200
    data = first.json()
    assert data["ok"] is True and data["cached"] is False
    assert data["structured"]["interpretacionMarkov"].startswith("BSS negativo")
    assert seen[0].headers["x-goog-api-key"] == "test-key"
    assert "test-key" not in first.text

    second = client.post("/api/ai/explain", json=BODY)
    assert second.json()["cached"] is True
    assert len(seen) == 1


def test_explain_maps_quota_error_to_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    _mock_gemini(monkeypatch, 429, {"error": {"message": "quota"}})
    response = client.post("/api/ai/explain", json=BODY)
    assert response.status_code == 429


def test_explain_rejects_malformed_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    _mock_gemini(monkeypatch, 200, {"candidates": [{"content": {"parts": [{"text": "no json"}]}}]})
    response = client.post("/api/ai/explain", json=BODY)
    assert response.status_code == 502


def test_explain_validates_mode() -> None:
    response = client.post("/api/ai/explain", json={"mode": "otro", "payload": {}})
    assert response.status_code == 422


def test_health_reports_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/api/health").json()["hasGeminiKey"] is False
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert client.get("/api/health").json()["hasGeminiKey"] is True
