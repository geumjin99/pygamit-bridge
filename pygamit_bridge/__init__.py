"""
PyGAMIT-Bridge — a lightweight, pure-Python orchestration layer around GAMIT/GLOBK.

It does not replace GAMIT/GLOBK or its native scripts (sh_get_rinex,
sh_rename_rinex3, makexp). Instead it wraps them into a single scriptable,
reproducible workflow and adds capabilities that the GAMIT distribution does
not provide out of the box:

1. Authenticated, batch retrieval of RINEX and IGS products from CDDIS, with
   silent-failure detection (HTML login pages, truncated/non-gzip downloads).
2. Pre-processing helpers that prepare multi-GNSS RINEX 3 and modern long-name
   IGS products for a GAMIT run, plus optional RINEX 3 -> 2.11 conversion and a
   makex batch-file fallback for legacy/edge-case setups.
3. Automatic generation of GAMIT station.info from RINEX headers.
4. Standardised extraction of ZTD, coordinates, baselines and quality metrics
   from GAMIT output files into tidy CSV/JSON for downstream analysis.

The package uses only the Python standard library.
"""

__version__ = '0.2.0'
__author__ = 'Jinzhen Han'
