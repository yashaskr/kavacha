# Data Acquisition Matrix

Extraction plan per source family. Prefer direct CSV/CKAN over HTML scraping.

## OpenCity crime packages (`family: opencity`)

| Field | Value |
|---|---|
| Method | CKAN `package_show` + resource HTTP download |
| Steps | 1) `GET /api/3/action/package_show?id={package}` 2) Download CSV/PDF resources 3) Store under `data/raw/{source_id}/{YYYY-MM-DD}/` 4) Append lineage.jsonl |
| Incremental | Date-partitioned folders; skip identical sha256 |
| Retry | tenacity exponential backoff |
| Normalize | Wide year columns → `crime_aggregate_fact`; filter Bengaluru for statewide files |

## OpenCity GIS (`family: gis_opencity`)

| Field | Value |
|---|---|
| Method | Same CKAN flow |
| Target | `data/reference/{source_id}/{YYYY-MM-DD}/` |
| Formats | KML, CSV, PDF, GeoJSON, ZIP |
| Normalize | File inventory only in Phase 1 (no crime join yet) |

## India Data Portal (`family: india_data_portal`)

| Field | Value |
|---|---|
| Method | Direct CSV HTTP download |
| URL | Resource download link in `sources.yaml` |
| Steps | Download → raw → parse district CAW → filter Karnataka + Bengaluru aliases |
| Years | 2017–2022 in current file |

## data.gov.in (`family: data_gov_in`)

| Field | Value |
|---|---|
| Method | Best-effort catalog page parse + public file link download |
| Limitation | Catalog API often needs API key; downloads may be gated |
| Steps | Save HTML pages → extract `.csv/.zip` links → download what is public |
| Future | `DATA_GOV_IN_API_KEY` authenticated Catalog API client |

## NCRB PDFs (`family: ncrb_pdf`)

| Field | Value |
|---|---|
| Method | Discover PDF links from NCRB Crime in India pages → download |
| Steps | 1) Fetch landing pages 2) Extract PDF URLs 3) Download CII volumes |

## NCRB CAW backfill 2012-2016 (`family: ncrb_backfill`)

| Field | Value |
|---|---|
| Method | Download chapter/table PDFs + district XLSX from NCRB table-content/chapter pages; extract Bengaluru rows |
| Steps | 1) `collect --source ncrb_backfill` 2) `normalize` runs `ncrb_extract` (pdfplumber text + openpyxl) 3) Facts land in `crime_aggregate_fact` for years 2012-2016 |
| Priority files | `5-crime-against-women_YYYY.pdf`, `Table-5.1_YYYY.pdf`, district CAW `.xlsx`, 2016 full publication Table 3B.* |
| Output | City/district aggregates only (not street-level) |

## india-geodata GitHub (`family: gis_github`)

| Field | Value |
|---|---|
| Method | Direct release asset HTTP download |
| Artifacts | `KGISMAPS_KN_Police_Station_Boundaries.parquet` (+ optional pmtiles) |
| Target | `data/reference/` |

## Tier C sources

| Family | Method |
|---|---|
| media / judicial / synthetic | **None** — inventory only |

## Storage & lineage rules

1. Never overwrite differing content; hash-suffix if changed.
2. Every download appends `lineage.jsonl` with URL, time, sha256, status.
3. Staging is regenerable from raw via `normalize`.
4. No victim PII fields are collected.

## CLI

```bash
python -m src.cli collect
python -m src.cli collect --source opencity
python -m src.cli normalize
python -m src.cli report
python -m src.cli run-all
```
