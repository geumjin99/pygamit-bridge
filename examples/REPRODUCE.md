# Reproducing the illustrative example

This recipe regenerates the three-station high-latitude example bundled with
this repository (solution-quality metrics and daily-mean ZTD) from scratch
against a local GAMIT/GLOBK installation. The network is the two Antarctic
stations MCM4 (McMurdo) and SYOG (Syowa) tied to the mid-latitude global IGS
station AUCK (Auckland). A pre-extracted `examples/results.json` from this run
is committed alongside this file as a reference output.

## Prerequisites

- GAMIT/GLOBK ≥ 10.6 installed and on `PATH` (`~/gg`); 10.71 used here.
- `CRX2RNX` (Hatanaka) on `PATH`.
- A NASA Earthdata account with CDDIS access. Put credentials in `~/.netrc`:
  ```
  machine urs.earthdata.nasa.gov login <USER> password <PASS>
  ```
- PyGAMIT-Bridge installed: `pip install -e .` from the repo root.

## Example configuration

| Item | Value |
|------|-------|
| Date | 2024 DOY 001 (1 Jan 2024) |
| Stations | AUCK, MCM4, SYOG |
| Orbits | IGS final |
| GAMIT version | 10.71 |
| Experiment name (`--expt`) | `anta` |

## Steps

```bash
# 0. workspace
export EXPT=./expt/2024001
mkdir -p $EXPT/tables

# 1. authenticated batch download (RINEX + IGS products)
pygamit-bridge download --stations auck,mcm4,syog \
    --year 2024 --start-doy 1 --end-doy 1 \
    --output ./data/rinex --products-output ./data/products

# 2-5. stage data, build station.info, write batch fallback
python3 examples/process_day.py --year 2024 --doy 1 \
    --stations auck,mcm4,syog \
    --data-dir ./data/rinex --products-dir ./data/products \
    --expt-dir $EXPT --expt anta

# 6. copy/edit the GAMIT control tables into $EXPT/tables as usual
#    (process.defaults, sestbl., sittbl., sites.defaults). station.info is
#    already generated in $EXPT/tables/station.info by step 2-5.

# 7. run GAMIT
cd $EXPT && sh_gamit -expt anta -d 2024 1 -orbit IGSF -nogifs >& sh_gamit.log
cd -

# 8. extract analysis-ready results
pygamit-bridge parse --session-dir $EXPT/001 --expt anta -o results.json
pygamit-bridge parse --session-dir $EXPT/001 --expt anta -o ztd.csv

# 9. (optional) aggregate several session-days into a ZTD time series
pygamit-bridge aggregate ./expt/2024*/001 --expt anta -o ztd_timeseries.csv
```

## Interpreting `results.json`

`results.json` contains the structured fields summarised below:

- **Solution-quality metrics**: `summary.num_observations`,
  `summary.num_parameters` / `live_parameters`, `summary.nrms`,
  `summary.postfit_nrms`, `summary.wl_rate` / `wl_fixed` / `num_ambiguities`,
  `summary.nl_rate` / `nl_fixed`.
- **Daily-mean ZTD**: the `ztd` records with `epoch_idx == 0` give the
  per-station daily-mean `ztd_mm` and `sigma_mm`; the count of distinct
  `epoch_idx > 0` segments is the number of resolved piecewise segments.
  `parser.summarize_ztd()` returns exactly these per-station fields
  (`ztd_daily_mm`, `sigma_mm`, `n_segments`), and `pygamit-bridge aggregate`
  emits one row per station-day across many sessions.

> Note: exact figures depend on the GAMIT version, the IGS product vintage at
> download time, and control-table settings, so small differences from the
> committed `results.json` are expected and should simply be reported as
> produced.
