"""Tests for the citizen reports API."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_citizen_report_lifecycle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CITIZEN_REPORTS_DATABASE", str(tmp_path / "reports.db"))
    client = TestClient(app)
    payload = {
        "latitude": 6.2442,
        "longitude": -75.5812,
        "sector": "Valle de Aburrá [Medellín]",
        "intensity": "Alta",
        "note": "Humo visible cerca de la ladera.",
        "role": "habitante o testigo",
        "experience": None,
        "name": "Ana",
        "contact": "ana@example.test",
    }

    created = client.post("/api/citizen-reports", json=payload)
    assert created.status_code == 201
    report = created.json()
    assert report["status"] == "pendiente"
    assert report["name"] == "Ana"

    listed = client.get("/api/citizen-reports")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    report_id = report["id"]

    updated = client.patch(
        f"/api/citizen-reports/{report_id}", json={"status": "verificado"}
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "verificado"

    deleted = client.delete(f"/api/citizen-reports/{report_id}")
    assert deleted.status_code == 204
    assert client.get("/api/citizen-reports").json()["count"] == 0


def test_citizen_report_validates_coordinates_and_note(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CITIZEN_REPORTS_DATABASE", str(tmp_path / "reports.db"))
    client = TestClient(app)

    response = client.post(
        "/api/citizen-reports",
        json={
            "latitude": 91,
            "longitude": -75,
            "intensity": "Alta",
            "note": "x",
            "role": "habitante o testigo",
        },
    )

    assert response.status_code == 422
