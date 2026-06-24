"""Unit tests for pygamit_bridge.converter (RINEX 3 -> 2.11 shim)."""

from pygamit_bridge import converter
from tests import rinex_fixtures as fx


def test_obs_mapping_examples():
    assert converter.OBS_MAPPING['C1C'] == 'C1'
    assert converter.OBS_MAPPING['C1W'] == 'P1'
    assert converter.OBS_MAPPING['C2W'] == 'P2'
    assert converter.OBS_MAPPING['L2W'] == 'L2'
    assert converter.OBS_MAPPING['L5I'] == 'L5'


def test_header_parsing_keeps_per_system_obs():
    lines = fx.rinex3_file().splitlines(keepends=True)
    header = converter._parse_rinex3_header(lines)
    assert header['version'].startswith('3')
    assert header['marker_name'] == 'CAS1'
    assert header['obs_types']['G'] == ['C1C', 'L1C', 'D1C', 'S1C', 'C2W', 'L2W']
    assert header['obs_types']['R'] == ['C1C', 'L1C', 'C2C', 'L2C']


def test_convert_produces_rinex2(tmp_path):
    src = tmp_path / "in.rnx"
    dst = tmp_path / "out.obs"
    src.write_text(fx.rinex3_file())

    assert converter.convert_rinex3_to_rinex2(str(src), str(dst)) is True

    out = dst.read_text()
    lines = out.splitlines()
    # Version line is RINEX 2.11.
    assert lines[0][0:9].strip() == '2.11'
    assert 'RINEX VERSION / TYPE' in lines[0]
    # GPS-only: GLONASS satellites must not appear in the data section.
    assert 'R01' not in out
    assert 'G05' in out
    # Obs types are mapped to 2-char codes; C2W -> P2 is present.
    types_line = next(l for l in lines if '# / TYPES OF OBSERV' in l)
    assert 'P2' in types_line


def test_rinex2_passthrough(tmp_path):
    src = tmp_path / "in2.obs"
    dst = tmp_path / "out2.obs"
    src.write_text(fx.RINEX2_FILE)
    assert converter.convert_rinex3_to_rinex2(str(src), str(dst)) is True
    # Pass-through copies content unchanged.
    assert dst.read_text() == fx.RINEX2_FILE
