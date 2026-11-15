"""CSV adapters for the official IDEAM and NASA FIRMS source files.

Faithful replication of ``parseIdeamCsv`` and ``parseFirmsCsv`` from the
reference application. The IDEAM schema is verified against the official
``METADATOS.txt`` of https://puntosdecalor.ideam.gov.co/archivos-csv/:
``;`` delimiter, comma decimals, UTC-5 timestamps, temperatures in °C.

Rows with invalid coordinates or timestamps are skipped without hiding the
rest of the file; no source values are rewritten.
"""

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from app.schemas.hotspot import HotspotObservation
from app.utils.geo import (
    Bbox,
    cot_local_to_utc_iso,
    infer_department_and_municipality,
    is_within_bbox,
    parse_locale_decimal,
)

FRP_UNAVAILABLE_FLAG = "FRP_UNAVAILABLE_OR_LT_1MW"
BRIGHTNESS_UNAVAILABLE_FLAG = "BRIGHTNESS_UNAVAILABLE"
LOW_CONFIDENCE_FLAG = "LOW_CONFIDENCE"
IDEAM_REFERENCE_URL = "https://puntosdecalor.ideam.gov.co/archivos-csv/"
FIRMS_REFERENCE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/"


class ParsedRowCounts(TypedDict):
    rows_total: int
    rows_skipped: int


def _split_lines(csv_text: str) -> list[str]:
    normalized = csv_text.replace("\r\n", "\n").replace("\r", "\n")
    return [line for line in normalized.split("\n") if line.strip()]


def _normalize_confidence(raw: str | int | None, sensor: str) -> tuple[str, int]:
    """Provisional display heuristic replicated from the reference app.

    This mapping is a presentation convenience, not the approved
    scientific normalization of MODIS/VIIRS confidence (F4 is still
    blocked on that decision).
    """
    if raw is None or raw == "":
        return "nominal", 50
    if isinstance(raw, int) or (isinstance(raw, str) and raw.strip().isdigit()):
        number = int(raw)
        if number < 30:
            return "low", number
        if number >= 80:
            return "high", number
        return "nominal", number
    text = str(raw).strip().lower()
    if text in {"h", "high", "alta"}:
        return "high", 90 if sensor == "VIIRS" else 85
    if text in {"l", "low", "baja"}:
        return "low", 20
    return "nominal", 60


def _parse_fuente_field(fuente: str) -> tuple[str, str]:
    """Derive sensor and satellite from the IDEAM ``fuente`` column."""
    upper = fuente.upper()
    if "MODIS" in upper:
        if "AQUA" in upper:
            return "MODIS", "Aqua"
        if "TERRA" in upper:
            return "MODIS", "Terra"
        return "MODIS", "Terra/Aqua"
    if "VIIRS" in upper:
        if "NOAA-21" in upper or "NOAA21" in upper or "N21" in upper:
            return "VIIRS", "NOAA-21"
        if "NOAA-20" in upper or "NOAA20" in upper or "N20" in upper:
            return "VIIRS", "NOAA-20"
        return "VIIRS", "Suomi-NPP"
    return "UNKNOWN", fuente or "Desconocido"


def _text_at(row: list[str], index: int) -> str:
    """Return the stripped cell at ``index`` or an empty string when missing."""
    if index < 0 or index >= len(row):
        return ""
    return row[index].strip()


def _decimal_at(row: list[str], index: int) -> float | None:
    """Return the parsed decimal cell at ``index`` or None when missing."""
    if index < 0 or index >= len(row):
        return None
    return parse_locale_decimal(row[index])


def _float_at(row: list[str], index: int) -> float | None:
    """Return the plain float cell at ``index`` or None when missing/invalid."""
    if index < 0 or index >= len(row) or row[index] == "":
        return None
    try:
        return float(row[index])
    except ValueError:
        return None


def parse_ideam_csv(
    csv_text: str,
    bbox: Bbox | None = None,
    ingested_at: str | None = None,
    file_ref: str | None = None,
) -> list[HotspotObservation]:
    """Parse one official IDEAM daily CSV into hotspot observations."""
    lines = _split_lines(csv_text)
    if len(lines) < 2:
        return []

    delimiter = ";" if ";" in lines[0] else ","
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    rows = list(reader)
    headers = [header.strip().lower() for header in rows[0]]

    def _find(predicate) -> int:
        return next((index for index, header in enumerate(headers) if predicate(header)), -1)

    idx_fecha = _find(lambda h: "fecha" in h)
    idx_lat = _find(lambda h: h in {"lat", "latitude"})
    idx_lon = _find(lambda h: h in {"lon", "longitude"})
    idx_fuente = _find(lambda h: "fuente" in h)
    idx_temp1 = _find(lambda h: h == "temperatura (c)")
    idx_temp2 = _find(lambda h: "alt" in h)
    idx_frp = _find(lambda h: "radiación" in h or "radiacion" in h or "frp" in h)
    idx_conf = _find(lambda h: "confianza" in h)
    idx_day_night = _find(lambda h: "captura" in h or "dia-noche" in h)
    idx_scan = _find(lambda h: "scan" in h)
    idx_track = _find(lambda h: "track" in h)

    if idx_fecha < 0 or idx_lat < 0 or idx_lon < 0:
        return []

    ingested = ingested_at or ""
    observations: list[HotspotObservation] = []
    reference_url = file_ref or IDEAM_REFERENCE_URL

    for row in rows[1:]:
        if len(row) < 4:
            continue
        lat = _decimal_at(row, idx_lat)
        lon = _decimal_at(row, idx_lon)
        if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            continue
        if not is_within_bbox(lat, lon, bbox):
            continue

        time_info = cot_local_to_utc_iso(_text_at(row, idx_fecha))
        if time_info is None:
            continue

        fuente_raw = _text_at(row, idx_fuente) or "UNKNOWN"
        sensor, satellite = _parse_fuente_field(fuente_raw)

        temp1_c = _decimal_at(row, idx_temp1)
        temp2_c = _decimal_at(row, idx_temp2)
        brightness_k = round(temp1_c + 273.15, 2) if temp1_c is not None else None
        secondary_brightness_k = round(temp2_c + 273.15, 2) if temp2_c is not None else None

        frp_raw = _decimal_at(row, idx_frp)
        confidence_raw_text = _text_at(row, idx_conf)
        confidence_level, confidence_score = _normalize_confidence(
            confidence_raw_text or None, sensor
        )

        day_night_raw = _text_at(row, idx_day_night).upper()
        daynight: str | None = day_night_raw if day_night_raw in {"D", "N"} else None

        scan_km = _decimal_at(row, idx_scan)
        track_km = _decimal_at(row, idx_track)

        quality_flags: list[str] = []
        if frp_raw is None:
            quality_flags.append(FRP_UNAVAILABLE_FLAG)
        if brightness_k is None:
            quality_flags.append(BRIGHTNESS_UNAVAILABLE_FLAG)
        if confidence_level == "low":
            quality_flags.append(LOW_CONFIDENCE_FLAG)

        department, municipality = infer_department_and_municipality(lat, lon)
        cot_formatted = time_info["cot_formatted"]
        observation_id = (
            f"IDEAM_{sensor}_{cot_formatted.replace('-', '').replace(':', '').replace(' ', '')}"
            f"_{lat:.4f}_{lon:.4f}"
        )
        observations.append(
            HotspotObservation(
                id=observation_id,
                observation_id=observation_id,
                latitude=round(lat, 5),
                longitude=round(lon, 5),
                acquired_at=time_info["utc_iso"],
                observed_at_utc=time_info["utc_iso"],
                observed_at_local_cot=cot_formatted,
                acq_date=cot_formatted[:10],
                acq_time=time_info["hhmm"],
                sensor=sensor,
                satellite=satellite,
                instrument=sensor,
                confidence_raw=confidence_raw_text or None,
                confidence_level=confidence_level,
                confidence_score=confidence_score,
                frp_mw=round(frp_raw, 2) if frp_raw is not None else None,
                brightness_k=brightness_k,
                secondary_brightness_k=secondary_brightness_k,
                scan_km=scan_km,
                track_km=track_km,
                daynight=daynight,
                concordance="single_sensor",
                department=department,
                municipality=municipality,
                source=f"IDEAM ({fuente_raw})",
                source_origin="IDEAM",
                verification_status=None,
                quality_flags=quality_flags,
                ingested_at=ingested,
                reference_url=reference_url,
                is_synthetic=False,
            )
        )
    return observations


def parse_firms_csv(
    csv_text: str,
    firms_product_label: str = "NASA_FIRMS",
    bbox: Bbox | None = None,
    ingested_at: str | None = None,
) -> list[HotspotObservation]:
    """Parse a NASA FIRMS CSV (Area API or public South America feeds)."""
    lines = _split_lines(csv_text)
    if len(lines) < 2:
        return []

    rows = list(csv.reader(io.StringIO("\n".join(lines))))
    headers = [header.strip().lower() for header in rows[0]]
    try:
        i_lat = headers.index("latitude")
        i_lon = headers.index("longitude")
        i_date = headers.index("acq_date")
        i_time = headers.index("acq_time")
    except ValueError:
        return []

    def _index(name: str) -> int:
        return headers.index(name) if name in headers else -1

    i_bright = next((headers.index(h) for h in ("brightness", "bright_ti4") if h in headers), -1)
    i_bright2 = next((headers.index(h) for h in ("bright_t31", "bright_ti5") if h in headers), -1)
    i_scan = _index("scan")
    i_track = _index("track")
    i_sat = _index("satellite")
    i_inst = _index("instrument")
    i_conf = _index("confidence")
    i_frp = _index("frp")
    i_day_night = _index("daynight")

    ingested = ingested_at or ""
    observations: list[HotspotObservation] = []

    for row in rows[1:]:
        if len(row) <= max(i_lat, i_lon, i_date):
            continue
        try:
            lat = float(row[i_lat])
            lon = float(row[i_lon])
        except (ValueError, IndexError):
            continue
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            continue
        if not is_within_bbox(lat, lon, bbox):
            continue

        acq_date = row[i_date].strip()
        acq_time_raw = _text_at(row, i_time) or "0000"
        acq_time_raw = acq_time_raw.zfill(4)
        if not acq_time_raw.isdigit():
            acq_time_raw = "0000"
        acquired_at = f"{acq_date}T{acq_time_raw[:2]}:{acq_time_raw[2:4]}:00+00:00"
        try:
            datetime.fromisoformat(acquired_at)
        except ValueError:
            continue

        cot_str = _utc_to_cot_string(acquired_at)

        sat_raw = _text_at(row, i_sat)
        sat_upper = sat_raw.upper()
        inst_raw = _text_at(row, i_inst).upper()
        hint = f"{inst_raw} {sat_upper} {firms_product_label.upper()}"

        sensor = "UNKNOWN"
        if "VIIRS" in hint or sat_upper in {"N", "NPP", "N20", "N21", "1", "2"}:
            sensor = "VIIRS"
        elif "MODIS" in hint or sat_upper in {"T", "A", "TERRA", "AQUA"}:
            sensor = "MODIS"

        if sat_upper == "T":
            satellite = "Terra"
        elif sat_upper == "A":
            satellite = "Aqua"
        elif sat_upper in {"N", "NPP"}:
            satellite = "Suomi-NPP"
        elif sat_upper in {"N20", "1"}:
            satellite = "NOAA-20"
        elif sat_upper in {"N21", "2"}:
            satellite = "NOAA-21"
        else:
            satellite = sat_raw

        confidence_raw = _text_at(row, i_conf) or None
        confidence_level, confidence_score = _normalize_confidence(confidence_raw, sensor)

        frp_value = _float_at(row, i_frp)
        brightness1 = _float_at(row, i_bright)
        brightness2 = _float_at(row, i_bright2)
        scan_km = _float_at(row, i_scan)
        track_km = _float_at(row, i_track)
        daynight: str | None = _text_at(row, i_day_night) or None
        if daynight not in {"D", "N"}:
            daynight = None

        department, municipality = infer_department_and_municipality(lat, lon)
        observation_id = (
            f"FIRMS_{firms_product_label}_{acq_date.replace('-', '')}_{acq_time_raw}"
            f"_{lat:.4f}_{lon:.4f}"
        )
        observations.append(
            HotspotObservation(
                id=observation_id,
                observation_id=observation_id,
                latitude=round(lat, 5),
                longitude=round(lon, 5),
                acquired_at=acquired_at,
                observed_at_utc=acquired_at,
                observed_at_local_cot=cot_str,
                acq_date=acq_date,
                acq_time=acq_time_raw,
                sensor=sensor,
                satellite=satellite or "FIRMS",
                instrument=sensor,
                confidence_raw=confidence_raw,
                confidence_level=confidence_level,
                confidence_score=confidence_score,
                frp_mw=round(frp_value, 2) if frp_value is not None else None,
                brightness_k=round(brightness1, 2) if brightness1 is not None else None,
                secondary_brightness_k=round(brightness2, 2) if brightness2 is not None else None,
                scan_km=scan_km,
                track_km=track_km,
                daynight=daynight,
                concordance="single_sensor",
                department=department,
                municipality=municipality,
                source=f"NASA FIRMS ({firms_product_label})",
                source_origin="NASA_FIRMS",
                verification_status=None,
                quality_flags=["FRP_UNAVAILABLE"] if frp_value is None else [],
                ingested_at=ingested,
                reference_url=FIRMS_REFERENCE_URL,
                is_synthetic=False,
            )
        )
    return observations


def _utc_to_cot_string(utc_iso: str) -> str:
    parsed = datetime.fromisoformat(utc_iso)
    cot = parsed.astimezone(UTC) - timedelta(hours=5)
    return cot.strftime("%Y-%m-%d %H:%M")
