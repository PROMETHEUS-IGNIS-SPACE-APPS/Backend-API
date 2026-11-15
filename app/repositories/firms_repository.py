"""Ingestion repository for the NASA FIRMS public NRT South America feeds.

Uses the public 7-day Earthdata CSV feeds (no MAP_KEY required), exactly
as the reference application does when no FIRMS Area key is configured:

- MODIS C6.1 7d
- VIIRS NOAA-20 (J1) C2 7d
- VIIRS NOAA-21 (J2) C2 7d

Feeds are fetched concurrently, cached in memory with a TTL, filtered by
bounding box during parsing, and reported per-feed so services can expose
degraded mode honestly.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from app.repositories.http_fetch import (
    CLIENT_USER_AGENT,
    fetch_text_with_retry,
)
from app.schemas.hotspot import HotspotObservation
from app.utils.geo import Bbox
from app.utils.parsing import parse_firms_csv

PUBLIC_FEEDS: tuple[dict[str, str], ...] = (
    {
        "id": "MODIS_C6_1_7d",
        "label": "MODIS_C6_1_South_America_7d",
        "url": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/"
        "MODIS_C6_1_South_America_7d.csv",
    },
    {
        "id": "VIIRS_NOAA20_7d",
        "label": "J1_VIIRS_C2_South_America_7d",
        "url": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/"
        "J1_VIIRS_C2_South_America_7d.csv",
    },
    {
        "id": "VIIRS_NOAA21_7d",
        "label": "J2_VIIRS_C2_South_America_7d",
        "url": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-21-viirs-c2/csv/"
        "J2_VIIRS_C2_South_America_7d.csv",
    },
)
FIRMS_FEED_TIMEOUT_SECONDS = 14.0
FIRMS_FEED_RETRIES = 2
CACHE_TTL_SECONDS = 15 * 60.0


@dataclass
class FirmsFeedsResult:
    """Outcome of fetching the public FIRMS feeds for a bounding box."""

    observations: list[HotspotObservation] = field(default_factory=list)
    loaded_feeds: list[str] = field(default_factory=list)
    failed_feeds: list[str] = field(default_factory=list)


class FirmsRepository:
    """Download, cache and parse the public FIRMS South America CSV feeds."""

    def __init__(self) -> None:
        self._feed_cache: dict[str, tuple[float, str]] = {}

    async def fetch_public_feeds(self, bbox: Bbox) -> FirmsFeedsResult:
        """Fetch all public feeds in parallel and parse them against ``bbox``."""
        ingested_at = datetime.now(UTC).isoformat()
        async with _client() as client:
            outcomes = await asyncio.gather(
                *(self._fetch_feed(client, feed, bbox, ingested_at) for feed in PUBLIC_FEEDS)
            )
        observations: list[HotspotObservation] = []
        loaded_feeds: list[str] = []
        failed_feeds: list[str] = []
        for feed, (parsed, failure) in zip(PUBLIC_FEEDS, outcomes, strict=True):
            if parsed is None:
                failed_feeds.append(f"{feed['id']} ({failure})")
            else:
                observations.extend(parsed)
                loaded_feeds.append(feed["id"])
        return FirmsFeedsResult(
            observations=observations,
            loaded_feeds=loaded_feeds,
            failed_feeds=failed_feeds,
        )

    async def _fetch_feed(
        self,
        client: httpx.AsyncClient,
        feed: dict[str, str],
        bbox: Bbox,
        ingested_at: str,
    ) -> tuple[list[HotspotObservation] | None, str]:
        """Fetch and parse one public feed; return (parsed, failure reason)."""
        cache_hit = self._feed_cache.get(feed["id"])
        if cache_hit is not None and time.monotonic() - cache_hit[0] < CACHE_TTL_SECONDS:
            return parse_firms_csv(cache_hit[1], feed["id"], bbox=bbox, ingested_at=ingested_at), ""
        try:
            response = await fetch_text_with_retry(
                client,
                feed["url"],
                timeout_seconds=FIRMS_FEED_TIMEOUT_SECONDS,
                retries=FIRMS_FEED_RETRIES,
            )
        except httpx.TransportError as error:
            return None, str(error)
        if response.status_code != 200 or "latitude,longitude" not in response.text:
            return None, f"HTTP {response.status_code}"
        self._feed_cache[feed["id"]] = (time.monotonic(), response.text)
        return parse_firms_csv(response.text, feed["id"], bbox=bbox, ingested_at=ingested_at), ""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": CLIENT_USER_AGENT})
