"""Ingestion repository for the official IDEAM daily hotspot CSVs.

The IDEAM portal publishes one CSV per day at
``https://puntosdecalor.ideam.gov.co/archivos-csv/Puntos_de_calor_Colombia_<date>.csv``.
This repository downloads the requested date window concurrently, caches
each daily file in memory with a TTL, and reports which files loaded and
which failed so services can decide on degraded mode transparently.

Security note: the IDEAM server omits an intermediate CA certificate
(the reference application documents the same workaround), so requests
to this specific host use a TLS context that does not verify the chain.
The context is scoped exclusively to IDEAM requests.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from app.repositories.http_fetch import (
    CLIENT_USER_AGENT,
    build_ssl_context,
    fetch_text_with_retry,
)
from app.schemas.hotspot import HotspotObservation
from app.utils.geo import (
    IDEAM_MAX_DAYS_PER_QUERY,
    Bbox,
    enumerate_date_range,
    extract_ideam_dates_from_index,
)
from app.utils.parsing import parse_ideam_csv

IDEAM_INDEX_URL = "https://puntosdecalor.ideam.gov.co/archivos-csv/"
IDEAM_FILE_URL_TEMPLATE = (
    "https://puntosdecalor.ideam.gov.co/archivos-csv/Puntos_de_calor_Colombia_{date}.csv"
)
IDEAM_DAILY_CONCURRENCY = 6
IDEAM_SAMPLE_CONCURRENCY = 16
IDEAM_FILE_TIMEOUT_SECONDS = 12.0
IDEAM_FILE_RETRIES = 2
IDEAM_SAMPLE_TIMEOUT_SECONDS = 4.5
IDEAM_SAMPLE_RETRIES = 0
CACHE_TTL_SECONDS = 15 * 60.0


@dataclass
class IdeamWindowResult:
    """Outcome of fetching a date window from the IDEAM portal."""

    observations: list[HotspotObservation] = field(default_factory=list)
    loaded_files: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)
    dates_count: int = 0


@dataclass
class IdeamDirectoryResult:
    """Outcome of reading the IDEAM portal file index."""

    total_files: int
    all_dates: list[str]


def ideam_file_name(date: str) -> str:
    """Name of the daily IDEAM file for a given date."""
    return f"Puntos_de_calor_Colombia_{date}.csv"


DIRECTORY_LATEST_DATES_LIMIT = 30


class IdeamRepository:
    """Download, cache and parse the official IDEAM daily CSV files."""

    def __init__(self) -> None:
        self._daily_cache: dict[str, tuple[float, str]] = {}

    async def fetch_directory(self) -> IdeamDirectoryResult:
        """Read the portal index and list the available daily file dates."""
        async with self._client() as client:
            response = await fetch_text_with_retry(
                client, IDEAM_INDEX_URL, timeout_seconds=10.0, retries=0
            )
        if response.status_code >= 400:
            raise RuntimeError(f"IDEAM HTTP {response.status_code}")
        latest_dates = extract_ideam_dates_from_index(response.text)
        return IdeamDirectoryResult(total_files=len(latest_dates), all_dates=sorted(latest_dates))

    async def fetch_window(self, from_date: str, to_date: str, bbox: Bbox) -> IdeamWindowResult:
        """Download and parse the daily files covering the inclusive date range."""
        dates = enumerate_date_range(from_date, to_date)
        if not dates:
            raise ValueError(
                "Rango de fechas inválido (use YYYY-MM-DD, "
                f"máximo {IDEAM_MAX_DAYS_PER_QUERY} días por consulta)."
            )
        return await self.fetch_dates(
            dates,
            bbox,
            concurrency=IDEAM_DAILY_CONCURRENCY,
            timeout_seconds=IDEAM_FILE_TIMEOUT_SECONDS,
            retries=IDEAM_FILE_RETRIES,
        )

    async def fetch_dates(
        self,
        dates: list[str],
        bbox: Bbox,
        *,
        concurrency: int,
        timeout_seconds: float,
        retries: int,
    ) -> IdeamWindowResult:
        """Download and parse a list of specific dates with bounded concurrency."""
        semaphore = asyncio.Semaphore(concurrency)
        ingested_at = datetime.now(UTC).isoformat()
        async with self._client() as client:
            outcomes = await asyncio.gather(
                *(
                    self._fetch_single_day(
                        client,
                        date,
                        bbox,
                        semaphore,
                        ingested_at=ingested_at,
                        timeout_seconds=timeout_seconds,
                        retries=retries,
                    )
                    for date in dates
                )
            )
        observations: list[HotspotObservation] = []
        loaded_files: list[str] = []
        failed_files: list[str] = []
        for date, parsed, failure in outcomes:
            if parsed is None:
                failed_files.append(f"{ideam_file_name(date)} ({failure})")
            else:
                observations.extend(parsed)
                loaded_files.append(ideam_file_name(date))
        return IdeamWindowResult(
            observations=observations,
            loaded_files=sorted(loaded_files),
            failed_files=failed_files,
            dates_count=len(dates),
        )

    async def _fetch_single_day(
        self,
        client: httpx.AsyncClient,
        date: str,
        bbox: Bbox,
        semaphore: asyncio.Semaphore,
        ingested_at: str,
        timeout_seconds: float,
        retries: int,
    ) -> tuple[str, list[HotspotObservation] | None, str]:
        """Fetch and parse one daily file; return (date, parsed, failure reason)."""
        cache_hit = self._daily_cache.get(date)
        if cache_hit is not None and time.monotonic() - cache_hit[0] < CACHE_TTL_SECONDS:
            return (
                date,
                parse_ideam_csv(
                    cache_hit[1], bbox=bbox, ingested_at=ingested_at, file_ref=_file_url(date)
                ),
                "",
            )
        async with semaphore:
            try:
                response = await fetch_text_with_retry(
                    client,
                    _file_url(date),
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                )
            except httpx.TransportError as error:
                return date, None, str(error)
        if response.status_code != 200 or ";" not in response.text:
            return date, None, f"HTTP {response.status_code}"
        self._daily_cache[date] = (time.monotonic(), response.text)
        return (
            date,
            parse_ideam_csv(
                response.text, bbox=bbox, ingested_at=ingested_at, file_ref=_file_url(date)
            ),
            "",
        )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"User-Agent": CLIENT_USER_AGENT},
            verify=build_ssl_context(verify=False),
        )


def _file_url(date: str) -> str:
    return IDEAM_FILE_URL_TEMPLATE.format(date=date)
