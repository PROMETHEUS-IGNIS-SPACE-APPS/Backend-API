"""Shared helpers for the ingestion HTTP routes."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

INGEST_ERROR_LOGGER = logger


def default_date_window(days: int = 44, to_date: str | None = None) -> tuple[str, str]:
    """Return ``(from, to)`` covering the last ``days`` days up to today (COT)."""
    if to_date is None:
        to_date = (datetime.now(UTC) - timedelta(hours=5)).strftime("%Y-%m-%d")
    try:
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError(f"Fecha inválida: {to_date!r}. Use el formato YYYY-MM-DD.") from error
    from_dt = to_dt - timedelta(days=days)
    return from_dt.strftime("%Y-%m-%d"), to_date


def ingestion_error_response(
    error: Exception,
    message: str,
    status_code: int = 502,
    *,
    log: logging.Logger | None = None,
) -> JSONResponse:
    """Build the documented ``{"ok": false, "error": ...}`` failure payload."""
    (log or logger).warning("Ingestion endpoint error: %s", error)
    return JSONResponse(status_code=status_code, content={"ok": False, "error": message})
