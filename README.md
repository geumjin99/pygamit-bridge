# PyGAMIT-Bridge

**A Python toolkit for automated GAMIT/GLOBK processing with modern RINEX and IGS product formats.**

Since the IGS transition to long filenames (GPS Week 2238, Nov 2022) and the widespread adoption of RINEX 3/4, GAMIT users face three compatibility challenges that this toolkit addresses.

## Problem Statement

| Challenge | Impact | Solution Module |
|-----------|--------|----------------|
| CDDIS Earthdata authentication | wget/curl returns HTML login pages instead of data | `downloader` |
| GAMIT's `makexp` cannot parse RINEX 3 headers | X-file generation fails, processing chain breaks | `converter` + `batch_fallback` |
| Scattered output format (o-file, q-file, etc.) | No standardized data extraction | `parser` |

## Installation

```bash
git clone https://github.com/geumjin99/pygamit-bridge.git
cd pygamit-bridge
pip install -e .
```

### Prerequisites
- Python ≥ 3.7 (standard library only, no third-party dependencies)
- GAMIT/GLOBK 10.71 installed
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

### 2. Convert RINEX 3 → 2
```bash
pygamit-bridge convert \
    --input MCM400ATA_R_20250010000_01D_30S_MO.rnx \
    --output mcm40010.25o
```

### 3. Preprocess for GAMIT
```bash
pygamit-bridge preprocess \
    --year 2025 --doy 1 \
    --data-dir ./data/rinex \
    --products-dir ./data/products \
    --expt-dir ./gamit/expt/2025001 \
    --gg-dir ~/gg
```

### 4. Parse Results
```bash
# After running sh_gamit:
pygamit-bridge parse \
    --session-dir ./gamit/expt/2025001 \
    --output results.json
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
```

## Architecture

```
pygamit_bridge/
├── downloader.py       # Module 1: CDDIS smart download with Earthdata auth
├── converter.py        # Module 2a: RINEX 3 → RINEX 2.11 format bridge
├── batch_fallback.py   # Module 2b: makexp batch file fallback generator
├── preprocessor.py     # Module 2c: Product filename mapping & preparation
├── parser.py           # Module 3: Standardized GAMIT output parser
├── cli.py              # Unified CLI interface
└── utils.py            # GPS time utilities
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Citation

This toolkit is described in the following paper, currently under review:

> Han, J. (2025). PyGAMIT-Bridge: A Python Toolkit for Automated GAMIT/GLOBK
> Processing with Modern RINEX and IGS Product Formats.
> *GPS Solutions* (GPS Toolbox), under review.

A BibTeX entry will be provided once the paper is published.
