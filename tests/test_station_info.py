"""Unit tests for pygamit_bridge.station_info."""

from pygamit_bridge import station_info
from tests import rinex_fixtures as fx


def test_build_entry_from_rinex3(tmp_path):
    rnx = tmp_path / "cas10010.25o"
    rnx.write_text(fx.rinex3_file())
    entry = station_info.build_entry(str(rnx))

    assert entry['SITE'] == 'cas1'
    assert entry['Station Name'] == 'CAS1'
    assert entry['Session Start'] == '2025 001 00 00 00'
    assert entry['Session Stop'] == '2025 001 23 59 30'
    assert entry['Ant Ht'] == '0.0083'
    assert entry['HtCod'] == 'DHARP'
    assert entry['Receiver Type'] == 'SEPT POLARX5'
    assert entry['Antenna Type'] == 'SEPCHOKE_B3E6'
    assert entry['Dome'] == 'SPKE'
    assert entry['Receiver SN'] == '3001234'


def test_generate_station_info_file(tmp_path):
    rnx = tmp_path / "cas10010.25o"
    rnx.write_text(fx.rinex3_file())
    out = tmp_path / "station.info"

    n = station_info.generate_station_info([str(rnx)], str(out))
    assert n == 1

    text = out.read_text()
    lines = text.splitlines()
    # Header line is a comment keyed by GAMIT column labels.
    assert lines[0].startswith('*SITE')
    assert 'Station Name' in lines[0]
    assert 'Receiver Type' in lines[0]
    assert 'Antenna Type' in lines[0]
    # Data line carries the site code and metadata.
    assert any('cas1' in l and 'SEPT POLARX5' in l for l in lines[1:])


def test_header_and_data_columns_align(tmp_path):
    """Each data field must start at its header keyword column."""
    rnx = tmp_path / "cas10010.25o"
    rnx.write_text(fx.rinex3_file())
    out = tmp_path / "station.info"
    station_info.generate_station_info([str(rnx)], str(out))
    lines = out.read_text().splitlines()
    header, data = lines[0], lines[1]
    # 'Receiver Type' keyword column should contain the receiver in the data row.
    col = header.index('Receiver Type')
    assert data[col:col + 12].strip().startswith('SEPT')
