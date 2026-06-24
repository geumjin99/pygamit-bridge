"""
station_info.py — generate a GAMIT ``station.info`` from RINEX headers.

GAMIT requires a ``station.info`` file describing, for each occupation, the
receiver/antenna metadata and the antenna height. Building it by hand (or
keeping it in sync with the data actually downloaded) is a recurring chore, and
the GAMIT distribution does not ship a stand-alone tool that derives it directly
from a set of RINEX files. This module fills that gap.

It reads the standard header records that are *identical* in RINEX 2 and RINEX 3
(``MARKER NAME``, ``REC # / TYPE / VERS``, ``ANT # / TYPE``,
``ANTENNA: DELTA H/E/N``, ``TIME OF FIRST/LAST OBS``) and emits a GAMIT-style
``station.info`` whose columns are keyed by the conventional header line so that
GAMIT's free-format reader (``lib/rstnfo.f``) can locate each field.

Antenna height is written under the ``DHARP`` height code (height measured to the
antenna reference point), which is what ``ANTENNA: DELTA H/E/N`` reports.
"""

import os
import glob
from datetime import datetime

from .utils import date_to_doy


# Column layout: (header label, field width). Header and data rows are built
# from the same spec so that values always sit under their header keyword.
_COLUMNS = [
    ('*SITE', 5),
    ('Station Name', 16),
    ('Session Start', 17),
    ('Session Stop', 17),
    ('Ant Ht', 8),
    ('HtCod', 6),
    ('Ant N', 8),
    ('Ant E', 8),
    ('Receiver Type', 20),
    ('Vers', 20),
    ('SwVer', 6),
    ('Receiver SN', 20),
    ('Antenna Type', 16),
    ('Dome', 5),
    ('Antenna SN', 12),
]


def _read_header_records(path):
    """Read the labelled header records shared by RINEX 2 and RINEX 3.

    Returns a dict with the metadata needed for station.info. Works on plain
    (uncompressed) RINEX observation files.
    """
    info = {
        'marker_name': '',
        'rec_serial': '', 'rec_type': '', 'rec_vers': '',
        'ant_serial': '', 'ant_type': '',
        'delta_hen': (0.0, 0.0, 0.0),
        'time_first': None, 'time_last': None,
    }
    with open(path, 'r', errors='replace') as f:
        for line in f:
            label = line[60:].strip() if len(line) > 60 else ''
            if label == 'END OF HEADER':
                break
            if label == 'MARKER NAME':
                info['marker_name'] = line[0:60].strip()
            elif label == 'REC # / TYPE / VERS':
                info['rec_serial'] = line[0:20].strip()
                info['rec_type'] = line[20:40].strip()
                info['rec_vers'] = line[40:60].strip()
            elif label == 'ANT # / TYPE':
                info['ant_serial'] = line[0:20].strip()
                info['ant_type'] = line[20:40]  # keep columns for radome split
            elif label == 'ANTENNA: DELTA H/E/N':
                try:
                    h = float(line[0:14]); e = float(line[14:28]); n = float(line[28:42])
                    info['delta_hen'] = (h, e, n)
                except ValueError:
                    pass
            elif label == 'TIME OF FIRST OBS':
                info['time_first'] = _parse_obs_time(line)
            elif label == 'TIME OF LAST OBS':
                info['time_last'] = _parse_obs_time(line)
    return info


def _parse_obs_time(line):
    """Parse a TIME OF FIRST/LAST OBS record into a datetime (UTC, no tz)."""
    try:
        year = int(line[0:6])
        month = int(line[6:12])
        day = int(line[12:18])
        hour = int(line[18:24])
        minute = int(line[24:30])
        sec = float(line[30:43])
        return datetime(year, month, day, hour, minute, int(sec))
    except (ValueError, IndexError):
        return None


def _gamit_time(dt):
    """Format a datetime as GAMIT 'YYYY DDD HH MM SS'."""
    year, doy = date_to_doy(dt)
    return f"{year:4d} {doy:03d} {dt.hour:02d} {dt.minute:02d} {dt.second:02d}"


def _split_antenna(ant_field):
    """Split the 20-char RINEX antenna field into (model, radome)."""
    model = ant_field[0:16].strip()
    dome = ant_field[16:20].strip() or 'NONE'
    return model, dome


def build_entry(path, site=None):
    """Build a single station.info entry (dict of column -> value) from a RINEX file.

    Args:
        path: path to an uncompressed RINEX observation file.
        site: 4-char site code; if None, derived from the filename.

    Returns:
        dict keyed by the column labels in ``_COLUMNS`` (without the leading '*').
    """
    h = _read_header_records(path)

    if site is None:
        site = os.path.basename(path)[0:4]
    site = site.lower()

    start = h['time_first']
    stop = h['time_last']
    if start is None:
        # last resort: cannot date the occupation; leave blank-safe defaults
        start = datetime(1980, 1, 6, 0, 0, 0)
    if stop is None and start is not None:
        stop = start.replace(hour=23, minute=59, second=59)

    model, dome = _split_antenna(h['ant_type'])
    hh, ee, nn = h['delta_hen']

    # SwVer: best-effort numeric parse of the firmware version string.
    swver = '0.0'
    for tok in h['rec_vers'].replace(',', ' ').split():
        try:
            swver = f"{float(tok):.2f}"
            break
        except ValueError:
            continue

    return {
        'SITE': site,
        'Station Name': h['marker_name'] or site.upper(),
        'Session Start': _gamit_time(start),
        'Session Stop': _gamit_time(stop),
        'Ant Ht': f"{hh:.4f}",
        'HtCod': 'DHARP',
        'Ant N': f"{nn:.4f}",
        'Ant E': f"{ee:.4f}",
        'Receiver Type': h['rec_type'],
        'Vers': h['rec_vers'],
        'SwVer': swver,
        'Receiver SN': h['rec_serial'],
        'Antenna Type': model,
        'Dome': dome,
        'Antenna SN': h['ant_serial'],
    }


def _format_row(values, is_header):
    """Render one fixed-width row (header line or data line)."""
    cells = []
    for label, width in _COLUMNS:
        if is_header:
            text = label
        elif label == '*SITE':
            text = ' ' + str(values.get('SITE', '')).ljust(4)
        else:
            text = str(values.get(label, ''))
        cells.append(text.ljust(width)[:width])
    return ' '.join(cells).rstrip()


def header_line():
    """Return the GAMIT station.info column header line."""
    return _format_row(None, is_header=True)


def generate_station_info(rinex_files, output_path):
    """Generate a GAMIT station.info from a list of RINEX observation files.

    Args:
        rinex_files: iterable of paths to uncompressed RINEX (v2 or v3) files.
        output_path: path of the station.info file to write.

    Returns:
        number of entries written.
    """
    entries = []
    for path in rinex_files:
        try:
            entries.append(build_entry(path))
        except (IOError, OSError):
            continue

    # Deterministic order: by site then session start.
    entries.sort(key=lambda e: (e['SITE'], e['Session Start']))

    with open(output_path, 'w') as f:
        f.write(header_line() + '\n')
        for e in entries:
            f.write(_format_row(e, is_header=False) + '\n')

    return len(entries)


def generate_from_dir(rinex_dir, output_path, pattern='*.??o'):
    """Convenience wrapper: scan a directory for RINEX obs files and build station.info.

    Args:
        rinex_dir: directory containing RINEX observation files.
        output_path: station.info output path.
        pattern: glob pattern for RINEX obs files (default matches ssssddd0.yyo).

    Returns:
        number of entries written.
    """
    files = sorted(glob.glob(os.path.join(rinex_dir, pattern)))
    if not files:
        files = sorted(glob.glob(os.path.join(rinex_dir, '*.rnx')))
    return generate_station_info(files, output_path)
