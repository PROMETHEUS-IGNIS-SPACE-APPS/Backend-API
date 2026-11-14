"""Tests for the IDEAM and FIRMS CSV adapters."""

from app.utils.parsing import parse_firms_csv, parse_ideam_csv

IDEAM_CSV = (
    "Fecha (UTC-5);Lat;Lon;Fuente;Temperatura (C);Temperatura Alt* (C);"
    "Radiación térmica (MW);Confianza;Captura (Dia-Noche);"
    "Scan - real pixel size (km);Track - real pixel size (km)\n"  # noqa: E501
    "2026-11-10 06:58;7,98500;-75,19500;MODIS-Terra;312,85;295,00;12,5;80;D;1,05;1,02\n"  # noqa: E501
    "2026-11-10 07:15;6,24400;-75,58100;VIIRS-NOAA-20;325,00;307,00;;h;N;0,39;0,36\n"  # noqa: E501
    "bad-row-with-invalid-coords;999;-75,19500;MODIS;300,00;;5;Nominal;D;;\n"  # noqa: E501
    "2026-11-10 08:00;2,11500;-74,77100;VIIRS-SNPP;310,00;295,00;3,0;Nominal;D;0,44;0,46\n"  # noqa: E501
)

FIRMS_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
    "satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"  # noqa: E501
    "7.9850,-75.1950,340.1,0.39,0.36,2026-11-10,1258,N20,VIIRS,h,1.0NRT,315.2,8.4,D\n"  # noqa: E501
    "6.2440,-75.5810,330.0,1.05,1.02,2026-11-10,1259,T,,85,1.0NRT,310.0,15.7,N\n"  # noqa: E501
)


def test_parse_ideam_csv_parses_valid_rows() -> None:
    observations = parse_ideam_csv(IDEAM_CSV, ingested_at="2026-11-14T00:00:00+00:00")
    assert len(observations) == 3

    modis = observations[0]
    assert modis.observation_id.startswith("IDEAM_MODIS_")
    assert modis.sensor == "MODIS"
    assert modis.satellite == "Terra"
    assert modis.acquired_at == "2026-11-10T11:58:00+00:00"
    assert modis.observed_at_local_cot == "2026-11-10 06:58"
    assert modis.acq_date == "2026-11-10"
    assert modis.acq_time == "0658"
    assert modis.confidence_raw == "80"
    assert modis.confidence_level == "high"
    assert modis.confidence_score == 80
    assert modis.frp_mw == 12.5
    assert modis.brightness_k == 586.0
    assert modis.daynight == "D"
    assert modis.department == "Antioquia"
    assert modis.municipality == "Caucasia"
    assert modis.source_origin == "IDEAM"
    assert modis.is_synthetic is False
    assert modis.quality_flags == []

    viirs = observations[1]
    assert viirs.sensor == "VIIRS"
    assert viirs.satellite == "NOAA-20"
    assert viirs.confidence_raw == "h"
    assert viirs.confidence_level == "high"
    assert viirs.confidence_score == 90
    assert viirs.frp_mw is None
    assert "FRP_UNAVAILABLE_OR_LT_1MW" in viirs.quality_flags

    nominal = observations[2]
    assert nominal.sensor == "VIIRS"
    assert nominal.satellite == "Suomi-NPP"
    assert nominal.confidence_raw == "Nominal"
    assert nominal.confidence_level == "nominal"
    assert nominal.confidence_score == 60
    assert nominal.frp_mw == 3.0


def test_parse_ideam_csv_skips_invalid_and_out_of_bbox_rows() -> None:
    all_rows = parse_ideam_csv(IDEAM_CSV)
    bbox = {"west": -79.2, "south": -4.3, "east": -66.8, "north": 12.6}
    limited = parse_ideam_csv(IDEAM_CSV, bbox=bbox)
    # Invalid coordinate row is skipped in both cases; all remaining rows are in-bbox.
    assert len(all_rows) == 3
    assert len(limited) == 3


def test_parse_ideam_csv_bbox_filter_excludes_outside_points() -> None:
    antioquia = {"west": -77.35, "south": 5.4, "east": -73.85, "north": 8.95}
    observations = parse_ideam_csv(IDEAM_CSV, bbox=antioquia)
    # Caucasia (7.985) and Medellín (6.244) are inside; Caquetá (2.115) is outside.
    assert [observation.municipality for observation in observations] == [
        "Caucasia",
        "Medellín",
    ]


def test_parse_ideam_csv_requires_required_columns() -> None:
    assert parse_ideam_csv("Fuente;Temperatura\nMODIS;300\n") == []
    assert parse_ideam_csv("") == []


def test_parse_firms_csv_parses_viirs_and_modis_rows() -> None:
    observations = parse_firms_csv(
        FIRMS_CSV, "MODIS_C6_1_7d", ingested_at="2026-11-14T00:00:00+00:00"
    )
    assert len(observations) == 2

    viirs = observations[0]
    assert viirs.observation_id.startswith("FIRMS_MODIS_C6_1_7d_")
    assert viirs.sensor == "VIIRS"
    assert viirs.satellite == "NOAA-20"
    assert viirs.acquired_at == "2026-11-10T12:58:00+00:00"
    assert viirs.observed_at_local_cot == "2026-11-10 07:58"
    assert viirs.confidence_raw == "h"
    assert viirs.frp_mw == 8.4
    assert viirs.brightness_k == 340.1
    assert viirs.secondary_brightness_k == 315.2
    assert viirs.daynight == "D"
    assert viirs.source_origin == "NASA_FIRMS"
    assert viirs.is_synthetic is False

    modis = observations[1]
    assert modis.sensor == "MODIS"
    assert modis.satellite == "Terra"
    assert modis.confidence_raw == "85"
    assert modis.confidence_level == "high"
    assert modis.confidence_score == 85
    assert modis.frp_mw == 15.7
    assert modis.brightness_k == 330.0
    assert modis.secondary_brightness_k == 310.0
    assert modis.daynight == "N"
    assert modis.instrument == "MODIS"


def test_parse_firms_csv_requires_required_columns() -> None:
    assert parse_firms_csv("satellite,frp\nT,10\n") == []
    assert parse_firms_csv("") == []
