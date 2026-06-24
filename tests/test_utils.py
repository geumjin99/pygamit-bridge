"""Unit tests for pygamit_bridge.utils."""

from datetime import datetime

from pygamit_bridge import utils


def test_doy_roundtrip():
    assert utils.doy_to_date(2025, 1) == datetime(2025, 1, 1)
    assert utils.doy_to_date(2024, 60) == datetime(2024, 2, 29)  # leap year
    assert utils.date_to_doy(datetime(2025, 1, 1)) == (2025, 1)
    assert utils.date_to_doy(datetime(2024, 12, 31)) == (2024, 366)


def test_gps_week_anchors():
    # Bulletproof anchors around the GPS epoch (1980-01-06 = week 0, day 0).
    assert utils.date_to_gps_week(1980, 1, 6) == (0, 0)
    assert utils.date_to_gps_week(1980, 1, 7) == (0, 1)
    assert utils.date_to_gps_week(1980, 1, 13) == (1, 0)
    # IGS long-filename transition: GPS week 2238 began Sunday 2022-11-27.
    assert utils.date_to_gps_week(2022, 11, 27) == (2238, 0)


def test_doy_to_gps_week():
    assert utils.doy_to_gps_week(2022, 331) == (2238, 0)  # 2022-11-27


def test_is_gzip(tmp_path):
    good = tmp_path / "a.gz"
    good.write_bytes(b"\x1f\x8b\x08\x00rest")
    bad = tmp_path / "b.gz"
    bad.write_bytes(b"<!DOCTYPE html><html>")
    assert utils.is_gzip(str(good)) is True
    assert utils.is_gzip(str(bad)) is False
    assert utils.is_gzip(str(tmp_path / "missing.gz")) is False


def test_is_html(tmp_path):
    page = tmp_path / "login"
    page.write_bytes(b"<!DOCTYPE html>\n<html><head>Earthdata Login</head>")
    data = tmp_path / "data"
    data.write_bytes(b"\x1f\x8b\x08\x00binary")
    assert utils.is_html(str(page)) is True
    assert utils.is_html(str(data)) is False


def test_station_name_short():
    assert utils.station_name_short("MCM400ATA") == "mcm4"
    assert utils.station_name_short("CAS100ATA_R_20250010000") == "cas1"
