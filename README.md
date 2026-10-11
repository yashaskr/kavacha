# Kavacha — Bengaluru Women's Safety Intelligence

Data-first pipeline that discovers, downloads, and stages publicly available
crimes-against-women statistics for Bengaluru / Karnataka, plus a static product UI (**Kavacha**).

> **Important:** India does not publish US-style open, geocoded FIR incident feeds.
> This corpus is primarily **city / district / category aggregates** plus GIS
> reference layers (wards, police stations, jurisdictions).

## Quick start

```bash
python -m pip install -r requirements.txt
set PYTHONPATH=%CD%
python -m src.cli collect
python -m src.cli normalize
python -m src.cli clean
python -m src.cli report
```

End-user files after `clean`:

- `data/staging/crime_annual_bengaluru_city.csv` (default product slice)
- `data/staging/crime_annual_totals.csv` (headline trend)
- `docs/data_dictionary.md`

If TLS verification fails on your machine (common with some Windows/proxy setups), either fix your CA store or temporarily set:

```bash
set WS_DATA_INSECURE_SSL=1
```

The collector also auto-retries once with `verify=False` after an SSL error.

## Product UI (Kavacha)

Thin static explorer over the canonical city dataset (no npm required):

```bash
python scripts/sync_web_data.py
cd web
python -m http.server 5180
```

Open http://localhost:5180 — brand **Kavacha**, totals trend with gap years marked, year category breakdown, quality/completeness badges, and a map (city pressure + station mode).

Map layers are prepared with `python scripts/prepare_map_layers.py` (also run by `sync_web_data.py`).

- **City pressure** mode uses city annual aggregates (available now).
- **Station detail** mode needs `data/staging/ps_crime.csv` → synced to `web/data/geo/ps_crime.csv` (see `docs/ps_level_data_spec.md`). Without it, station popups stay honest landmarks + city context.

## Live site (GitHub Pages)

The `web/` folder is published as a static site. After push to `main`, open:

**https://yashaskr.github.io/kavacha/**

(Repo: `https://github.com/yashaskr/kavacha`)

## Commands

| Command | Purpose |
|---------|---------|
| `collect` | Download Tier A/B online sources into `data/raw/` |
| `normalize` | Build staged `crime_aggregate_fact` + dims |
| `clean` | Build end-user canonical annual tables |
| `report` | Run QC and write `docs/coverage_report.md` |
| `collect --source opencity` | Collect only one source family |

## Layout

```
catalogs/sources.yaml   machine-readable source inventory
docs/                   human-readable inventory + coverage
data/raw/               immutable downloads (gitignored)
data/staging/           cleaned parquet/csv
data/reference/         GIS masters
src/collectors/         downloaders
src/normalize/          schema + taxonomy
src/qc/                 validation + coverage report
```

## License notes

Respect each source's license (NDSAP / public domain / portal ToS).
Do not republish victim-identifying material.
