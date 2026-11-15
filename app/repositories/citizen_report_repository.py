"""SQLite persistence for citizen reports."""

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.schemas.citizen_report import (
    CitizenReport,
    CitizenReportCreate,
    ReportStatus,
)

_DEFAULT_DATABASE = Path(__file__).resolve().parents[2] / "data" / "citizen_reports.db"


def _database_path() -> Path:
    return Path(os.environ.get("CITIZEN_REPORTS_DATABASE", str(_DEFAULT_DATABASE)))


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS citizen_reports (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            sector TEXT,
            intensity TEXT NOT NULL,
            note TEXT NOT NULL,
            role TEXT NOT NULL,
            experience TEXT,
            name TEXT,
            contact TEXT,
            status TEXT NOT NULL CHECK (status IN ('pendiente', 'verificado'))
        )
        """
    )
    connection.commit()
    return connection


def _to_model(row: sqlite3.Row) -> CitizenReport:
    return CitizenReport(
        id=UUID(row["id"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        latitude=row["latitude"],
        longitude=row["longitude"],
        sector=row["sector"],
        intensity=row["intensity"],
        note=row["note"],
        role=row["role"],
        experience=row["experience"],
        name=row["name"],
        contact=row["contact"],
        status=row["status"],
    )


def create_report(payload: CitizenReportCreate) -> CitizenReport:
    report_id = uuid4()
    created_at = datetime.now(UTC)
    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO citizen_reports (
                id, created_at, latitude, longitude, sector, intensity, note,
                role, experience, name, contact, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(report_id),
                created_at.isoformat(),
                payload.latitude,
                payload.longitude,
                payload.sector,
                payload.intensity,
                payload.note,
                payload.role,
                payload.experience,
                payload.name,
                payload.contact,
                "pendiente",
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM citizen_reports WHERE id = ?", (str(report_id),)
        ).fetchone()
        if row is None:
            raise RuntimeError("No fue posible leer el reporte recién creado.")
        return _to_model(row)
    finally:
        connection.close()


def list_reports(limit: int) -> list[CitizenReport]:
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT * FROM citizen_reports ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_to_model(row) for row in rows]
    finally:
        connection.close()


def update_status(report_id: UUID, status: ReportStatus) -> CitizenReport | None:
    connection = _connect()
    try:
        cursor = connection.execute(
            "UPDATE citizen_reports SET status = ? WHERE id = ?",
            (status, str(report_id)),
        )
        connection.commit()
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            "SELECT * FROM citizen_reports WHERE id = ?", (str(report_id),)
        ).fetchone()
        return _to_model(row) if row is not None else None
    finally:
        connection.close()


def delete_report(report_id: UUID) -> bool:
    connection = _connect()
    try:
        cursor = connection.execute(
            "DELETE FROM citizen_reports WHERE id = ?", (str(report_id),)
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()
