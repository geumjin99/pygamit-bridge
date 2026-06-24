"""Unit tests for pygamit_bridge.parser (GAMIT output extraction)."""

import json

from pygamit_bridge import parser
from tests import rinex_fixtures as fx


def _make_session(tmp_path):
    (tmp_path / "oanta.001").write_text(fx.OFILE)
    (tmp_path / "sh_anta.summary").write_text(fx.SUMMARY)
    return str(tmp_path)


def test_parse_ztd(tmp_path):
    session = _make_session(tmp_path)
    ztd = parser.parse_ztd(session, expt='anta')
    assert ztd, "expected ZTD records"
    daily = [r for r in ztd if r['epoch_idx'] == 0]
    assert len(daily) == 1
    assert daily[0]['station'] == 'CAS1'
    assert abs(daily[0]['ztd_m'] - 2.25488495) < 1e-6
    # Segment value is reconstructed as daily mean + adjustment (absolute ZTD).
    seg = [r for r in ztd if r['epoch_idx'] == 1][0]
    assert abs(seg['ztd_m'] - (2.25488495 + -0.02436935)) < 1e-6


def test_parse_positions(tmp_path):
    session = _make_session(tmp_path)
    pos = parser.parse_positions(session, expt='anta')
    assert 'CAS1' in pos
    assert pos['CAS1']['lat'] == 'S66:08:28.75536'
    assert pos['CAS1']['lon'] == 'E110:31:10.94408'
    assert abs(pos['CAS1']['radius_km'] - 6360.25875878) < 1e-4


def test_parse_summary(tmp_path):
    session = _make_session(tmp_path)
    s = parser.parse_summary(session, expt='anta')
    assert s['nrms'] == 0.41331
    assert s['postfit_nrms'] == 0.23542
    assert s['num_ambiguities'] == 89
    assert s['wl_fixed'] == 87 and s['nl_fixed'] == 76
    assert s['wl_rate'] == 97.8 and s['nl_rate'] == 85.4
    assert s['num_observations'] == 6110
    assert s['num_parameters'] == 268


def test_parse_summary_from_qfile(tmp_path):
    # No sh_gamit summary present -> metrics recovered from the q-file.
    (tmp_path / "qanta.001").write_text(fx.QFILE)
    s = parser.parse_summary(str(tmp_path), expt='anta')
    # First Prefit/Postfit pair (representative constrained solution).
    assert s['nrms'] == 0.77653
    assert s['postfit_nrms'] == 0.23629
    assert s['num_ambiguities'] == 59
    assert s['wl_fixed'] == 58 and s['nl_fixed'] == 40
    # Rates derived from counts.
    assert s['wl_rate'] == 98.3 and s['nl_rate'] == 67.8


def test_final_solution_preferred(tmp_path):
    # Both a preliminary ('p') and final ('a') o-file are present; the parser
    # must report the final solution and ignore the preliminary one.
    (tmp_path / "oantap.001").write_text(fx.OFILE_PREFIT)
    (tmp_path / "oantaa.001").write_text(fx.OFILE)
    ztd = parser.parse_ztd(str(tmp_path), expt='anta')
    daily = [r for r in ztd if r['epoch_idx'] == 0]
    assert len(daily) == 1
    assert abs(daily[0]['ztd_m'] - 2.25488495) < 1e-6  # not the 9.999 prefit


def test_summarize_ztd_dedupes_epochs(tmp_path):
    session = _make_session(tmp_path)
    summ = parser.summarize_ztd(parser.parse_ztd(session, expt='anta'))
    assert 'CAS1' in summ
    cas = summ['CAS1']
    assert cas['ztd_daily_mm'] == 2254.9  # daily-mean parameter (epoch 0)
    assert cas['n_segments'] == 1
    # Accepts the full parse_session dict too.
    summ2 = parser.summarize_ztd(parser.parse_session(session, expt='anta'))
    assert summ2['CAS1']['ztd_daily_mm'] == cas['ztd_daily_mm']


def test_aggregate_sessions(tmp_path):
    s1 = tmp_path / "d001"
    s2 = tmp_path / "d002"
    for d in (s1, s2):
        d.mkdir()
        (d / "oanta.001").write_text(fx.OFILE)
        (d / "sh_anta.summary").write_text(fx.SUMMARY)
    rows = parser.aggregate_sessions([str(s1), str(s2)],
                                     expt='anta', labels=['001', '002'])
    assert len(rows) == 2
    assert {r['session'] for r in rows} == {'001', '002'}
    r = rows[0]
    assert r['station'] == 'CAS1'
    assert r['postfit_nrms'] == 0.23542 and r['wl_rate'] == 97.8
    # Round-trip to CSV.
    out = tmp_path / "ts.csv"
    parser.export_timeseries_csv(rows, str(out))
    text = out.read_text()
    assert 'session,station,ztd_daily_mm' in text
    assert text.count('\n') == 3  # header + 2 rows


def test_aggregate_labels_length_mismatch(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        parser.aggregate_sessions([str(tmp_path)], labels=['a', 'b'])


def test_export_roundtrip(tmp_path):
    session = _make_session(tmp_path)
    results = parser.parse_session(session, expt='anta')
    jpath = tmp_path / "out.json"
    cpath = tmp_path / "out.csv"
    parser.export_json(results, str(jpath))
    parser.export_csv(results, str(cpath))
    loaded = json.loads(jpath.read_text())
    assert loaded['summary']['nrms'] == 0.41331
    assert 'station,epoch_idx' in cpath.read_text()
