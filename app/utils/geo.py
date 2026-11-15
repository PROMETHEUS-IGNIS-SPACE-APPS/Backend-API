"""Geospatial helpers replicated from the reference application (Ejemplo project).

Contains the bounding boxes used by the team, coordinate parsing, the
Colombia (UTC-5) local-time conversion, and the nearest-location
municipality inference. The region/bbox resolution rules must stay
byte-compatible with the reference so both frontends receive the same
results for the same query.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypedDict

ANTIOQUIA_BBOX_KEY = "antioquia"
ANTIOQUIA_IDEAM_BBOX_KEY = "antioquia_ideam"
COLOMBIA_BBOX_KEY = "colombia"
COLOMBIA_WIDE_BBOX_KEY = "colombia_wide"

IDEAM_MAX_DAYS_PER_QUERY = 90

_IDEAM_EXTENT_PATTERN = re.compile(r"Puntos_de_calor_Colombia_(\d{4}-\d{2}-\d{2})\.csv")
_COT_DATETIME_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?")


class Bbox(TypedDict):
    west: float
    south: float
    east: float
    north: float


@dataclass(frozen=True)
class ColombianLocation:
    municipality: str
    department: str
    subregion: str
    lat: float
    lon: float


# Reference centroids used to label observations with a municipality and
# department. Coordinates and names replicated from the reference data set.
COLOMBIA_LOCATIONS: tuple[ColombianLocation, ...] = (
    # Antioquia - Bajo Cauca & Nordeste (historically high thermal activity)
    ColombianLocation("Caucasia", "Antioquia", "Bajo Cauca", 7.985, -75.195),
    ColombianLocation("El Bagre", "Antioquia", "Bajo Cauca", 7.601, -74.808),
    ColombianLocation("Tarazá", "Antioquia", "Bajo Cauca", 7.585, -75.402),
    ColombianLocation("Zaragoza", "Antioquia", "Bajo Cauca", 7.491, -74.869),
    ColombianLocation("Segovia", "Antioquia", "Nordeste", 7.079, -74.701),
    ColombianLocation("Remedios", "Antioquia", "Nordeste", 7.027, -74.698),
    ColombianLocation("Amalfi", "Antioquia", "Nordeste", 6.911, -75.078),
    # Antioquia - Magdalena Medio & Urabá
    ColombianLocation("Puerto Berrío", "Antioquia", "Magdalena Medio", 6.491, -74.404),
    ColombianLocation("Yondó", "Antioquia", "Magdalena Medio", 7.045, -74.354),
    ColombianLocation("Turbo", "Antioquia", "Urabá", 8.093, -76.728),
    ColombianLocation("Apartadó", "Antioquia", "Urabá", 7.883, -76.634),
    ColombianLocation("Necoclí", "Antioquia", "Urabá", 8.424, -76.784),
    ColombianLocation("Mutatá", "Antioquia", "Urabá", 7.245, -76.435),
    # Antioquia - Norte, Occidente, Valle de Aburrá & Oriente
    ColombianLocation("Yarumal", "Antioquia", "Norte", 6.963, -75.417),
    ColombianLocation("Santa Rosa de Osos", "Antioquia", "Norte", 6.647, -75.461),
    ColombianLocation("Ituango", "Antioquia", "Norte", 7.172, -75.764),
    ColombianLocation("Dabeiba", "Antioquia", "Occidente", 7.001, -76.262),
    ColombianLocation("Frontino", "Antioquia", "Occidente", 6.779, -76.131),
    ColombianLocation("Medellín", "Antioquia", "Valle de Aburrá", 6.244, -75.581),
    ColombianLocation("Bello", "Antioquia", "Valle de Aburrá", 6.337, -75.558),
    ColombianLocation("Rionegro", "Antioquia", "Oriente", 6.155, -75.374),
    ColombianLocation("Sonsón", "Antioquia", "Oriente", 5.711, -75.311),
    # Other Colombian departments (national reference points)
    ColombianLocation("Puerto Gaitán", "Meta", "Llanos Orientales", 4.313, -72.081),
    ColombianLocation("Cumaribo", "Vichada", "Orinoquía", 4.445, -69.801),
    ColombianLocation("San Vicente del Caguán", "Caquetá", "Amazonía", 2.115, -74.771),
    ColombianLocation("Yopal", "Casanare", "Piedemonte", 5.337, -72.395),
    ColombianLocation("San José del Guaviare", "Guaviare", "Amazonía", 2.572, -72.646),
    ColombianLocation("Aracataca", "Magdalena", "Caribe", 10.591, -74.189),
)

ANTIOQUIA_BBOX: Bbox = Bbox(west=-77.35, south=5.4, east=-73.85, north=8.95)
COLOMBIA_BBOX: Bbox = Bbox(west=-79.2, south=-4.3, east=-66.8, north=12.6)
# Exact historical query extents supplied by the team.
ANTIOQUIA_IDEAM_EXTENT_BBOX: Bbox = Bbox(
    west=-78.73352, south=5.04717, east=-72.27356, north=9.24309
)
COLOMBIA_WIDE_IDEAM_EXTENT_BBOX: Bbox = Bbox(
    west=-81.2439, south=3.74367, east=-69.7522, north=10.53102
)


def parse_locale_decimal(raw: str | None) -> float | None:
    """Parse decimal numbers that use a comma separator (IDEAM files) or a dot."""
    if raw is None:
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    normalized = trimmed.replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def is_within_bbox(lat: float, lon: float, bbox: Bbox | None) -> bool:
    """Inclusive bounds check; a missing bbox accepts every coordinate."""
    if bbox is None:
        return True
    return bbox["south"] <= lat <= bbox["north"] and bbox["west"] <= lon <= bbox["east"]


def convert_ideam_extent_to_firms_bbox(extent_str: str) -> Bbox | None:
    """Convert an IDEAM URL extent `(North_West_South_East)` to FIRMS order.

    Example IDEAM param:
    ``(9.243092645104804_-78.73352050781251_5.04717073691972_-72.27355957031251)``
    """
    cleaned = extent_str.replace("(", "").replace(")", "").strip()
    parts = cleaned.split("_")
    if len(parts) != 4:
        return None
    try:
        north, west, south, east = (float(part) for part in parts)
    except ValueError:
        return None
    if west >= east or south >= north:
        return None
    if west < -180 or east > 180 or south < -90 or north > 90:
        return None
    return Bbox(
        west=round(west, 5), south=round(south, 5), east=round(east, 5), north=round(north, 5)
    )


def resolve_region_bbox(region: str, bbox_param: str | None = None) -> Bbox:
    """Resolve the effective bounding box from a region alias or explicit bbox.

    Explicit values accept FIRMS order ``west,south,east,north`` or the IDEAM
    extent form that contains underscore separators.
    """
    if bbox_param:
        if "_" in bbox_param:
            converted = convert_ideam_extent_to_firms_bbox(bbox_param)
            if converted is not None:
                return converted
        parts = [part for part in bbox_param.split(",")]
        try:
            numbers = [float(part) for part in parts]
        except ValueError:
            numbers = []
        if len(numbers) == 4:
            return Bbox(west=numbers[0], south=numbers[1], east=numbers[2], north=numbers[3])
    normalized = region.strip().lower()
    if normalized == COLOMBIA_BBOX_KEY:
        return COLOMBIA_BBOX
    if normalized == COLOMBIA_WIDE_BBOX_KEY:
        return COLOMBIA_WIDE_IDEAM_EXTENT_BBOX
    if normalized == ANTIOQUIA_IDEAM_BBOX_KEY:
        return ANTIOQUIA_IDEAM_EXTENT_BBOX
    return ANTIOQUIA_BBOX


def cot_local_to_utc_iso(cot_datetime: str) -> dict[str, str] | None:
    """Convert Colombia local date-time (``YYYY-MM-DD HH:MM``, UTC-5) to UTC ISO.

    The offset is fixed at +5 hours because Colombia has no daylight saving
    time; this avoids relying on the host OS timezone database.
    """
    match = _COT_DATETIME_PATTERN.match(cot_datetime.strip())
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(group) for group in match.groups(default="0"))
    try:
        naive = datetime(year, month, day, hour, minute, second)
        utc = (naive + timedelta(hours=5)).replace(tzinfo=UTC)
    except ValueError:
        return None
    utc_iso = utc.isoformat()
    return {
        "utc_iso": utc_iso,
        "utc_date": utc_iso[:10],
        "cot_formatted": f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
        "hhmm": f"{hour:02d}{minute:02d}",
    }


def infer_department_and_municipality(lat: float, lon: float) -> tuple[str, str]:
    """Assign the nearest known Colombian municipality/department label.

    Squared Euclidean distance on coordinates, with the Antioquia bounding
    check so out-of-region coordinates are not mislabeled.
    """
    best = COLOMBIA_LOCATIONS[0]
    best_distance_sq = float("inf")
    for location in COLOMBIA_LOCATIONS:
        d_lat = lat - location.lat
        d_lon = lon - location.lon
        distance_sq = d_lat * d_lat + d_lon * d_lon
        if distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
            best = location
    if best_distance_sq <= 0.16:
        return best.department, best.municipality
    if 5.4 <= lat <= 8.95 and -77.35 <= lon <= -73.85:
        return "Antioquia", f"Sector {best.municipality}"
    return "Colombia (Otras Regiones)", f"Ref. {best.municipality}"


def enumerate_date_range(
    start_date: str, end_date: str, max_days: int = IDEAM_MAX_DAYS_PER_QUERY
) -> list[str]:
    """List ISO dates (``YYYY-MM-DD``) between two inclusive date strings."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC)
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return []
    if start > end:
        return []
    dates: list[str] = []
    current = start
    one_day = timedelta(days=1)
    while current <= end and len(dates) < max_days:
        dates.append(current.strftime("%Y-%m-%d"))
        current += one_day
    return dates


def extract_ideam_dates_from_index(html_text: str) -> list[str]:
    """Extract the dates of the daily IDEAM CSV files listed in the portal index."""
    matches = set(_IDEAM_EXTENT_PATTERN.findall(html_text))
    return sorted(matches, reverse=True)
