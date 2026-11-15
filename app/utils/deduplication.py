"""Spatial-temporal deduplication and cross-sensor concordance tagging.

Replicates ``deduplicateObservations`` from the reference application:
exact duplicates are removed deterministically, and MODIS/VIIRS pairs of
the same thermal anomaly (~1.6 km, ±90 min) are explicitly tagged so a
single hotspot observed by two sensors is flagged instead of silently
overcounted. Results are sorted from newest to oldest.
"""

from datetime import UTC, datetime

from app.schemas.hotspot import HotspotObservation

COINCIDENCE_DEG = 0.015
COINCIDENCE_SECONDS = 90 * 60


def _event_time(observation: HotspotObservation) -> datetime:
    raw = observation.observed_at_utc or observation.acquired_at
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def deduplicate_observations(
    observations: list[HotspotObservation],
) -> list[HotspotObservation]:
    """Remove exact duplicates and tag cross-sensor concordance."""
    exact_seen: set[str] = set()
    unique: list[HotspotObservation] = []
    for observation in observations:
        key = (
            f"{observation.source_origin or 'SRC'}_{observation.satellite}"
            f"_{observation.acq_date}_{observation.acq_time}"
            f"_{observation.latitude:.4f}_{observation.longitude:.4f}"
        )
        if key in exact_seen:
            continue
        exact_seen.add(key)
        unique.append(observation.model_copy())

    times = [_event_time(observation) for observation in unique]
    for i, first in enumerate(unique):
        if first.sensor not in {"MODIS", "VIIRS"}:
            continue
        for j in range(i + 1, len(unique)):
            second = unique[j]
            if second.sensor == first.sensor or second.sensor not in {"MODIS", "VIIRS"}:
                continue
            if (
                abs(first.latitude - second.latitude) <= COINCIDENCE_DEG
                and abs(first.longitude - second.longitude) <= COINCIDENCE_DEG
            ):
                delta = abs((times[i] - times[j]).total_seconds())
                if delta <= COINCIDENCE_SECONDS:
                    concordance = (
                        "coincident_high"
                        if first.confidence_level == "high" or second.confidence_level == "high"
                        else "coincident_moderate"
                    )
                    first.concordance = concordance
                    second.concordance = concordance

    unique.sort(key=lambda observation: _event_time(observation), reverse=True)
    return unique
