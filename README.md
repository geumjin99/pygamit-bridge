# PyGAMIT-Bridge

**A lightweight, pure-Python orchestration layer around GAMIT/GLOBK.**

PyGAMIT-Bridge does **not** replace GAMIT/GLOBK or its native scripts
(`sh_get_rinex`, `sh_rename_rinex3`, `makexp`). Modern GAMIT (≥ 10.6) already
authenticates to CDDIS, renames RINEX 3 long filenames, and reads RINEX 3
natively. Instead, this toolkit wraps a GAMIT run into a single **scriptable,
reproducible workflow** and adds capabilities the distribution does not provide
out of the box.

## What it provides

| Capability | Why it helps | Module |
|-----------|--------------|--------|
| Authenticated **batch** retrieval from CDDIS with silent-failure detection (HTML login pages, non-gzip / truncated downloads) | One command for many stations × days; no half-downloaded junk silently breaking a run | `downloader` |
| Multi-GNSS RINEX 3 **pass-through** + long-name IGS product preparation; optional RINEX 3→2.11 conversion and `makex` batch fallback for legacy/edge cases | Keeps GLONASS/Galileo/BeiDou; reproducible staging without bespoke shell scripts | `preprocessor`, `converter`, `batch_fallback` |
| Automatic **`station.info`** generation directly from RINEX headers | Builds metadata from the RINEX files in hand, without requiring external IGS site logs | `station_info` |
| **Standardized extraction** of ZTD, coordinates, baselines and quality metrics into tidy CSV/JSON, plus multi-session **`aggregate`** into a ZTD time series | GAMIT results are scattered across Fortran fixed-width o/q/summary files | `parser` |

## Installation

```bash
git clone https://github.com/geumjin99/pygamit-bridge.git
cd pygamit-bridge
pip install -e .
```

### Prerequisites
- Python ≥ 3.7 (standard library only, no third-party runtime dependencies)
- GAMIT/GLOBK ≥ 10.6 installed (10.71 recommended; native RINEX 3 support)
- `CRX2RNX` utility (for Compact RINEX decompression)
- NASA Earthdata account (for CDDIS data access)

## Quick Start

### 1. Download Data
```bash
pygamit-bridge download \
    --stations mcm4,auck,syog,cas1 \
    --year 2025 --start-doy 1 --end-doy 7 \
    --output ./data/rinex \
    --products-output ./data/products
```

### 2. Preprocess for GAMIT (multi-GNSS RINEX 3 pass-through by default)
```bash
pygamit-bridge preprocess \
    --year 2025 --doy 1 \
    --data-dir ./data/rinex \
    --products-dir ./data/products \
    --expt-dir ./gamit/expt/2025001 \
    --gg-dir ~/gg
# add --convert-rinex2 only for legacy GAMIT (<10.6); this drops to GPS-only RINEX 2.11
```

### 3. Generate station.info from RINEX headers
```bash
pygamit-bridge stationinfo \
    --rinex-dir ./gamit/expt/2025001 \
    -o ./gamit/expt/2025001/tables/station.info
```

### 4. (Optional) Convert a single RINEX 3 file to 2.11 — legacy compatibility only
```bash
pygamit-bridge convert \
    --input MCM400ATA_R_20250010000_01D_30S_MO.rnx \
    --output mcm40010.25o
```

### 5. Parse Results
```bash
# After running sh_gamit:
pygamit-bridge parse \
    --session-dir ./gamit/expt/2025001 \
    --output results.json
```

### 6. Aggregate many sessions into a ZTD time series
```bash
# One tidy row per station-day, with per-session quality metrics:
pygamit-bridge aggregate ./gamit/expt/2025*/001 \
    --expt anta -o ztd_timeseries.csv
```

## Python API

```python
from pygamit_bridge.converter import convert_rinex3_to_rinex2
from pygamit_bridge.parser import parse_session, export_json

# Convert RINEX format
convert_rinex3_to_rinex2('input.rnx', 'output.obs')

# Parse GAMIT output
results = parse_session('./expt/2025001')
print(f"ZTD records: {len(results['ztd'])}")
print(f"nrms: {results['summary']['nrms']}")
export_json(results, 'results.json')

# Aggregate many session-days into a tidy ZTD time series
from pygamit_bridge.parser import aggregate_sessions, export_timeseries_csv
rows = aggregate_sessions(['./expt/2024001/001', './expt/2024002/001'])
export_timeseries_csv(rows, 'ztd_timeseries.csv')
```

## Architecture

```
pygamit_bridge/
├── downloader.py       # Authenticated batch download from CDDIS
├── preprocessor.py     # RINEX 3 pass-through + IGS product staging
├── converter.py        # Optional RINEX 3 → 2.11 shim (legacy GAMIT only)
├── batch_fallback.py   # Optional makex batch-file fallback (edge cases)
├── station_info.py     # station.info generation from RINEX headers
├── parser.py           # Standardized GAMIT output extraction (CSV/JSON)
├── cli.py              # Unified CLI interface
└── utils.py            # GPS time / file-validation utilities
```

## Testing

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Citation

If you use PyGAMIT-Bridge in your work, please cite the repository:

> Han, J. PyGAMIT-Bridge: a pure-Python orchestration layer for reproducible
> GAMIT/GLOBK processing with modern RINEX and IGS product formats.
> https://github.com/geumjin99/pygamit-bridge

An archival DOI will be added here in a future release.
