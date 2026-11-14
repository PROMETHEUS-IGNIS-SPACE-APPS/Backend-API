"""Tests for the geospatial helpers replicated from the reference app."""

from app.utils.geo import (
    ANTIOQUIA_BBOX,
    convert_ideam_extent_to_firms_bbox,
    cot_local_to_utc_iso,
    enumerate_date_range,
    extract_ideam_dates_from_index,
    infer_department_and_municipality,
    is_within_bbox,
    parse_locale_decimal,
    resolve_region_bbox,
)


def test_parse_locale_decimal_accepts_comma_and_dot() -> None:
    assert parse_locale_decimal("34,8") == 34.8
    assert parse_locale_decimal("-72,66096") == -72.66096
    assert parse_locale_decimal(" 7.5 ") == 7.5
    assert parse_locale_decimal("") is None
    assert parse_locale_decimal(None) is None
    assert parse_locale_decimal("abc") is None


def test_convert_ideam_extent_to_firms_bbox() -> None:
    extent = "(9.243092645104804_-78.73352050781251_5.04717073691972_-72.27355957031251)"
    converted = convert_ideam_extent_to_firms_bbox(extent)
    assert converted is not None
    assert converted["west"] == -78.73352
    assert converted["south"] == 5.04717
    assert converted["east"] == -72.27356
    assert converted["north"] == 9.24309


def test_convert_ideam_extent_rejects_invalid_values() -> None:
    assert convert_ideam_extent_to_firms_bbox("(3_10_5_20)") is None  # south >= north
    assert convert_ideam_extent_to_firms_bbox("(9.24_200_5.04_72)") is None  # out of range
    assert convert_ideam_extent_to_firms_bbox("(a_b_c_d)") is None
    assert convert_ideam_extent_to_firms_bbox("(10_20)") is None


def test_resolve_region_bbox_aliases_and_explicit() -> None:
    assert resolve_region_bbox("colombia")["west"] == -79.2
    assert resolve_region_bbox("antioquia_ideam")["north"] == 9.24309
    assert resolve_region_bbox("unknown-region") == ANTIOQUIA_BBOX
    explicit = resolve_region_bbox("antioquia", "-77,6,-75,5,-74,7,8")
    # Malformed (8 components) falls back to the region bbox.
    assert explicit == ANTIOQUIA_BBOX
    valid = resolve_region_bbox("antioquia", "-77.35,5.4,-73.85,8.95")
    assert valid == ANTIOQUIA_BBOX


def test_is_within_bbox_is_inclusive() -> None:
    assert is_within_bbox(5.4, -77.35, ANTIOQUIA_BBOX)
    assert is_within_bbox(8.95, -73.85, ANTIOQUIA_BBOX)
    assert not is_within_bbox(5.39, -75.0, ANTIOQUIA_BBOX)
    assert is_within_bbox(0.0, 0.0, None)


def test_cot_local_to_utc_iso_converts_fixed_offset() -> None:
    result = cot_local_to_utc_iso("2026-11-10 06:58")
    assert result is not None
    assert result["utc_iso"].startswith("2026-11-10T11:58:00")
    assert result["cot_formatted"] == "2026-11-10 06:58"
    assert result["hhmm"] == "0658"


def test_cot_local_to_utc_iso_rejects_invalid_input() -> None:
    assert cot_local_to_utc_iso("not-a-date") is None
    assert cot_local_to_utc_iso("") is None


def test_infer_department_and_municipality_near_reference() -> None:
    department, municipality = infer_department_and_municipality(7.985, -75.195)
    assert department == "Antioquia"
    assert municipality == "Caucasia"


def test_infer_department_and_municipality_inside_antioquia_only() -> None:
    department, municipality = infer_department_and_municipality(8.85, -77.3)
    assert department == "Antioquia"
    assert municipality.startswith("Sector ")


def test_infer_department_and_municipality_out_of_region() -> None:
    department, municipality = infer_department_and_municipality(-30.0, 150.0)
    assert department == "Colombia (Otras Regiones)"
    assert municipality.startswith("Ref. ")


def test_enumerate_date_range_inclusive_and_capped() -> None:
    dates = enumerate_date_range("2026-01-30", "2026-02-02")
    assert dates == ["2026-01-30", "2026-01-31", "2026-02-01", "2026-02-02"]
    assert enumerate_date_range("2026-02-10", "2026-02-01") == []
    assert enumerate_date_range("bad", "2026-02-01") == []
    assert enumerate_date_range("2026-01-01", "2026-12-31", max_days=5) == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-03",
        "2026-01-04",
        "2026-01-05",
    ]


def test_extract_ideam_dates_from_index() -> None:
    html = (
        "<a>Puntos_de_calor_Colombia_2026-11-13.csv</a>"
        "<a>Puntos_de_calor_Colombia_2026-11-12.csv</a>"
        "<a>Puntos_de_calor_Colombia_2024-01-01.csv</a>"
        "<a>other.csv</a>"
    )
    dates = extract_ideam_dates_from_index(html)
    assert dates == ["2026-11-13", "2026-11-12", "2024-01-01"]
