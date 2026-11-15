"""Application logic for real-data ingestion, fusion and degraded mode.

Coordinates the IDEAM and FIRMS repositories behind TTL response caches,
in-flight request deduplication, and on-disk snapshots that allow serving
the last authentic payload when remote sources fail. The payload shapes
replicate the reference application so both frontends receive identical
contracts.

Domain rules:
- No scientific harmonization happens here; records are parsed, deduplicated
  and tagged for cross-sensor concordance only.
- Degrading to a stored snapshot is always announced through
  ``degraded_mode`` and an explicit ``warning``; it is never silent.
- Failures of individual remote sources are surfaced, not hidden.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.repositories.firms_repository import (
    FirmsFeedsResult,
    FirmsRepository,
)
from app.repositories.ideam_repository import (
    DIRECTORY_LATEST_DATES_LIMIT,
    IdeamRepository,
    IdeamWindowResult,
)
from app.schemas.hotspot import HotspotObservation
from app.schemas.ingest import (
    AnyIngestResponse,
    BboxModel,
    FirmsResponse,
    FusionResponse,
    IdeamDirectoryResponse,
    IngestMetadata,
    ServiceStatus,
)
from app.services import ai_service
from app.utils.deduplication import deduplicate_observations
from app.utils.geo import (
    IDEAM_MAX_DAYS_PER_QUERY,
    Bbox,
    enumerate_date_range,
    resolve_region_bbox,
)

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 15 * 60.0
HISTORICAL_CACHE_TTL_SECONDS = CACHE_TTL_SECONDS * 2
HISTORICAL_ARCHIVE_START = "2024-01-01"
HISTORICAL_DENSE_WINDOW_DAYS = 45
HISTORICAL_MAX_RETURN = 9000

IDEAM_SOURCE_LABEL = "IDEAM - SMByC Colombia"
IDEAM_ATTRIBUTION = (
    "IDEAM - SMByC. Puntos de calor en Colombia (https://puntosdecalor.ideam.gov.co/). "
    "Fuente original: NASA LANCE FIRMS."
)
FIRMS_SOURCE_LABEL = (
    "NASA FIRMS Earthdata Public NRT 7d (MODIS C6.1 + VIIRS NOAA-20 + VIIRS NOAA-21)"
)
FIRMS_PUBLIC_WARNING = (
    "Usando feeds CSV públicos oficiales NASA FIRMS 7d (Sudamérica) filtrados a Colombia/Antioquia."
)
FUSION_ATTRIBUTION = (
    "IDEAM - SMByC Colombia (puntosdecalor.ideam.gov.co) + NASA LANCE FIRMS Earthdata "
    "(MODIS C6.1, VIIRS NOAA-20 & NOAA-21)."
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "data" / "cache"

_response_cache: dict[str, tuple[float, Any]] = {}
_inflight_tasks: dict[str, asyncio.Task[Any]] = {}

ideam_repository = IdeamRepository()
firms_repository = FirmsRepository()


async def _cache_or_run[ResponseT](
    key: str,
    ttl_seconds: float,
    factory: Callable[[], Awaitable[ResponseT]],
) -> tuple[ResponseT, bool]:
    """Serve a TTL cache hit, share in-flight work, or execute the factory.

    Returns the payload together with a flag telling whether it came from
    the TTL cache (in-flight sharing counts as fresh, like the reference).
    """
    hit = _response_cache.get(key)
    if hit is not None and time.monotonic() - hit[0] < ttl_seconds:
        result: ResponseT = hit[1]
        return result, True
    existing = _inflight_tasks.get(key)
    if existing is not None:
        return await existing, False
    task = asyncio.create_task(factory())
    _inflight_tasks[key] = task
    try:
        result = await task
    finally:
        _inflight_tasks.pop(key, None)
    _response_cache[key] = (time.monotonic(), result)
    return result, False


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def _cot_date_today() -> str:
    """Current calendar date in Colombia (UTC-5, no DST)."""
    return (datetime.now(UTC) - timedelta(hours=5)).strftime("%Y-%m-%d")


def _snapshot_path(name: str) -> Path:
    return SNAPSHOT_DIR / name


def _save_snapshot(name: str, response: AnyIngestResponse) -> None:
    """Persist the last authentic payload for degraded mode; failures are logged only."""
    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        _snapshot_path(name).write_text(response.model_dump_json(by_alias=True), encoding="utf-8")
    except OSError as error:
        logger.warning("Could not store ingestion snapshot %s: %s", name, error)


def _load_fusion_snapshot(name: str) -> FusionResponse | None:
    path = _snapshot_path(name)
    if not path.is_file():
        return None
    try:
        return FusionResponse.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        logger.warning("Could not read ingestion snapshot %s: %s", name, error)
        return None


def _load_firms_snapshot() -> FirmsResponse | None:
    path = _snapshot_path("last_firms.json")
    if not path.is_file():
        return None
    try:
        return FirmsResponse.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        logger.warning("Could not read FIRMS snapshot: %s", error)
        return None


async def get_ideam_observations(
    from_date: str, to_date: str, region: str, bbox_param: str | None
) -> FusionResponse:
    """Serve real IDEAM observations for an inclusive date range."""
    if not enumerate_date_range(from_date, to_date):
        raise ValueError(
            "Rango de fechas inválido (use YYYY-MM-DD, "
            f"máximo {IDEAM_MAX_DAYS_PER_QUERY} días por consulta)."
        )
    bbox = resolve_region_bbox(region, bbox_param)
    cache_key = f"ideam:{from_date}:{to_date}:{region}:{bbox_param or ''}"
    result, _ = await _cache_or_run(
        cache_key, CACHE_TTL_SECONDS, lambda: _run_ideam_window(from_date, to_date, region, bbox)
    )
    return result


async def _run_ideam_window(
    from_date: str, to_date: str, region: str, bbox: Bbox
) -> FusionResponse:
    window: IdeamWindowResult = await ideam_repository.fetch_window(from_date, to_date, bbox)
    if not window.loaded_files:
        snapshot = _load_fusion_snapshot("last_ideam.json")
        if snapshot is not None:
            return snapshot.model_copy(
                update={
                    "degraded_mode": True,
                    "warning": (
                        "El portal oficial del IDEAM no respondió temporalmente. Mostrando "
                        "último conjunto auténtico almacenado con su fecha original."
                    ),
                }
            )
        raise RuntimeError(
            "No fue posible descargar archivos CSV del IDEAM ("
            + ", ".join(window.failed_files)
            + ")"
        )
    deduplicated = deduplicate_observations(window.observations)
    payload = FusionResponse(
        degraded_mode=False,
        warning=(
            f"Algunos días no tuvieron archivo disponible: {', '.join(window.failed_files)}"
            if window.failed_files
            else None
        ),
        metadata=IngestMetadata(
            source=IDEAM_SOURCE_LABEL,
            fetched_at_utc=_now_utc(),
            from_=from_date,
            to=to_date,
            region=region,
            bbox=BboxModel(**bbox),
            files_loaded=window.loaded_files,
            raw_count=len(window.observations),
            deduplicated_count=len(deduplicated),
            attribution=IDEAM_ATTRIBUTION,
        ),
        observations=deduplicated,
    )
    _save_snapshot("last_ideam.json", payload)
    return payload


async def get_firms_observations(region: str, bbox_param: str | None) -> FirmsResponse:
    """Serve real NASA FIRMS observations from the public NRT feeds."""
    bbox = resolve_region_bbox(region, bbox_param)
    cache_key = f"firms:{region}:{bbox_param or ''}"
    result, _ = await _cache_or_run(
        cache_key, CACHE_TTL_SECONDS, lambda: _run_firms_public(bbox, region)
    )
    return result


async def _run_firms_public(bbox: Bbox, region: str) -> FirmsResponse:
    feeds: FirmsFeedsResult = await firms_repository.fetch_public_feeds(bbox)
    if not feeds.loaded_feeds:
        snapshot = _load_firms_snapshot()
        if snapshot is not None:
            return snapshot.model_copy(
                update={
                    "degraded_mode": True,
                    "warning": (
                        "NASA FIRMS no respondió temporalmente; mostrando último snapshot "
                        "NRT auténtico guardado."
                    ),
                }
            )
        raise RuntimeError(
            "No fue posible acceder a los feeds públicos de NASA FIRMS ("
            + ", ".join(feeds.failed_feeds)
            + ")"
        )
    deduplicated = deduplicate_observations(feeds.observations)
    payload = FirmsResponse(
        degraded_mode=None,
        public_nrt_mode=True,
        has_map_key=False,
        source=FIRMS_SOURCE_LABEL,
        feeds_loaded=feeds.loaded_feeds,
        bbox=BboxModel(**bbox),
        fetched_at_utc=_now_utc(),
        count=len(deduplicated),
        warning=FIRMS_PUBLIC_WARNING,
        observations=deduplicated,
    )
    if region == "colombia":
        _save_snapshot("last_firms.json", payload)
    return payload


async def get_fusion_observations(
    from_date: str, to_date: str, region: str, bbox_param: str | None
) -> FusionResponse:
    """Serve the multi-agency fusion of IDEAM and NASA FIRMS for a date range."""
    bbox = resolve_region_bbox(region, bbox_param)
    cache_key = f"fusion:{from_date}:{to_date}:{region}:{bbox_param or ''}"
    result, was_cached = await _cache_or_run(
        cache_key, CACHE_TTL_SECONDS, lambda: _run_fusion(from_date, to_date, region, bbox)
    )
    if was_cached:
        return result.model_copy(update={"cached": True})
    return result


async def _run_fusion(from_date: str, to_date: str, region: str, bbox: Bbox) -> FusionResponse:
    ideam_obs, ideam_files = await _fetch_ideam_safe(from_date, to_date, bbox)
    firms_obs, firms_feeds = await _fetch_firms_safe(bbox)

    if not ideam_obs and not firms_obs:
        snapshot = _load_fusion_snapshot("last_fusion.json")
        if snapshot is not None:
            return snapshot.model_copy(
                update={
                    "degraded_mode": True,
                    "warning": (
                        "Las fuentes remotas tardaron en responder; sirviendo último conjunto "
                        "auténtico fusionado desde respaldo local."
                    ),
                }
            )
        raise RuntimeError(
            "No se obtuvieron registros ni de IDEAM ni de NASA FIRMS para el "
            "rango/región solicitado."
        )
    if not ideam_obs:
        warning = "IDEAM no devolvió archivos en este intento; mostrando únicamente NASA FIRMS."
    elif not firms_obs:
        warning = "NASA FIRMS no respondió temporalmente; mostrando únicamente IDEAM."
    else:
        warning = None

    combined_raw = [*ideam_obs, *firms_obs]
    deduplicated = deduplicate_observations(combined_raw)
    fusion = FusionResponse(
        degraded_mode=not ideam_obs or not firms_obs,
        warning=warning,
        metadata=IngestMetadata(
            source=(
                "Fusión IDEAM ("
                f"{len(ideam_obs)} raw) + NASA FIRMS Public NRT ({len(firms_obs)} raw)"
            ),
            fetched_at_utc=_now_utc(),
            from_=from_date,
            to=to_date,
            region=region,
            bbox=BboxModel(**bbox),
            files_loaded=[*ideam_files, *firms_feeds],
            ideam_raw_count=len(ideam_obs),
            firms_raw_count=len(firms_obs),
            raw_count=len(combined_raw),
            deduplicated_count=len(deduplicated),
            attribution=FUSION_ATTRIBUTION,
        ),
        observations=deduplicated,
    )
    if region == "antioquia_ideam":
        _save_snapshot("last_fusion.json", fusion)
    return fusion


async def _fetch_ideam_safe(
    from_date: str, to_date: str, bbox: Bbox
) -> tuple[list[HotspotObservation], list[str]]:
    """Fetch IDEAM data; individual source failure yields empty results, as the reference does."""
    try:
        window = await ideam_repository.fetch_window(from_date, to_date, bbox)
    except Exception as error:
        logger.warning("IDEAM fetch failed during fusion: %s", error)
        return [], []
    return window.observations, window.loaded_files


async def _fetch_firms_safe(bbox: Bbox) -> tuple[list[HotspotObservation], list[str]]:
    try:
        feeds = await firms_repository.fetch_public_feeds(bbox)
    except Exception as error:
        logger.warning("FIRMS fetch failed during fusion: %s", error)
        return [], []
    return feeds.observations, feeds.loaded_feeds


async def get_historical_all(region: str, bbox_param: str | None) -> FusionResponse:
    """Serve the multi-year coverage: sampled archive cuts plus a dense recent window."""
    bbox = resolve_region_bbox(region, bbox_param)
    today_col = _cot_date_today()
    cache_key = f"histall:{region}:{today_col}:{bbox_param or ''}"
    base, _ = await _cache_or_run(
        cache_key, HISTORICAL_CACHE_TTL_SECONDS, lambda: _run_historical(region, bbox, today_col)
    )
    return base.model_copy(update={"cached": True})


async def _run_historical(region: str, bbox: Bbox, today_col: str) -> FusionResponse:
    dense_start = (
        datetime.strptime(today_col, "%Y-%m-%d").replace(tzinfo=UTC)
        - timedelta(days=HISTORICAL_DENSE_WINDOW_DAYS - 1)
    ).strftime("%Y-%m-%d")
    anchor_dates = await _select_archive_anchor_dates(dense_start)

    dense_task = asyncio.create_task(_run_fusion(dense_start, today_col, region, bbox))
    archive_task = asyncio.create_task(
        ideam_repository.fetch_dates(
            anchor_dates,
            bbox,
            concurrency=16,
            timeout_seconds=4.5,
            retries=0,
        )
    )
    dense_fusion, archive = await asyncio.gather(
        _safe(dense_task, "dense fusion"), _safe(archive_task, "archive sample")
    )
    archive_observations = archive.observations if archive is not None else []
    archive_files = sorted(archive.loaded_files) if archive is not None else []

    combined_raw = [*archive_observations, *(dense_fusion.observations if dense_fusion else [])]
    deduplicated = deduplicate_observations(combined_raw)
    truncated = len(deduplicated) > HISTORICAL_MAX_RETURN
    sliced = deduplicated[:HISTORICAL_MAX_RETURN]

    degraded = bool((dense_fusion is None or dense_fusion.degraded_mode) and not archive_files)
    if truncated:
        warning = (
            f"Histórico 2024-01-01 → {today_col} condensado a los "
            f"{HISTORICAL_MAX_RETURN:,} registros más recientes y puntos de control "
            "bimensuales para proteger el rendimiento del navegador.".replace(",", ".")
        )
    else:
        warning = (
            f"Histórico completo 2024-01-01 → {today_col}: "
            f"{HISTORICAL_DENSE_WINDOW_DAYS} días densos recientes + "
            f"{len(archive_files)} cortes archivísticos mensuales + NASA FIRMS 7d en vivo."
        )
    dense_metadata = dense_fusion.metadata if dense_fusion is not None else None
    return FusionResponse(
        degraded_mode=degraded,
        warning=warning,
        metadata=IngestMetadata(
            source=(f"Histórico Multi-Anual IDEAM (2024–{today_col[:4]}) + NASA FIRMS 7d"),
            fetched_at_utc=_now_utc(),
            from_=HISTORICAL_ARCHIVE_START,
            to=today_col,
            region=region,
            bbox=BboxModel(**bbox),
            files_loaded=[
                *archive_files,
                *(dense_metadata.files_loaded if dense_metadata else []),
            ],
            raw_count=len(combined_raw),
            deduplicated_count=len(sliced),
            attribution=(
                "IDEAM - SMByC Colombia (Archivo 2024-01-01 → Actualidad) "
                "+ NASA LANCE FIRMS Earthdata."
            ),
        ),
        observations=sliced,
    )


async def _select_archive_anchor_dates(dense_start: str) -> list[str]:
    """Pick one archive date per half-month slot from the IDEAM portal index."""
    try:
        directory = await ideam_repository.fetch_directory()
    except Exception as error:
        logger.warning("IDEAM directory listing failed for historical anchors: %s", error)
        return []
    candidates = sorted(
        date for date in directory.all_dates if HISTORICAL_ARCHIVE_START <= date < dense_start
    )
    picked: dict[str, str] = {}
    for date in candidates:
        year_month = date[:7]
        slot = f"{year_month}-{'H1' if int(date[8:10]) <= 15 else 'H2'}"
        picked.setdefault(slot, date)
    return sorted(picked.values())


async def _safe(task: asyncio.Task[Any], label: str) -> Any:
    """Await a task and convert failures into None with a logged reason."""
    try:
        return await task
    except Exception as error:
        logger.warning("%s failed: %s", label, error)
        return None


async def get_ideam_directory() -> IdeamDirectoryResponse:
    """List the daily IDEAM files currently published by the portal."""
    directory = await ideam_repository.fetch_directory()
    return IdeamDirectoryResponse(
        portal_url="https://puntosdecalor.ideam.gov.co/archivos-csv/",
        total_files=directory.total_files,
        latest_dates=directory.all_dates[:DIRECTORY_LATEST_DATES_LIMIT],
    )


def get_service_status() -> ServiceStatus:
    """Static capability summary of this deployment."""
    return ServiceStatus(
        service="NASA Fire Harmonization API - Public Data Ingest",
        timestamp_utc=_now_utc(),
        has_gemini_key=ai_service.has_api_key(),
        has_firms_key=False,
        firms_public_nrt_available=True,
        ideam_max_days_per_query=IDEAM_MAX_DAYS_PER_QUERY,
        citizen_reports_count=0,
    )
