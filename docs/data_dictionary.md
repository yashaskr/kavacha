# Data Dictionary — Canonical Women's Crime Statistics (Bengaluru)

This is the **end-user product dataset**. Prefer these files over raw extracts.

## Files

| File | Purpose |
|---|---|
| `data/staging/crime_annual_canonical.csv` | Full canonical table (all geos/categories) |
| `data/staging/crime_annual_bengaluru_city.csv` | Default product slice: Bengaluru City |
| `data/staging/crime_annual_totals.csv` | Annual totals only (best for headline trends) |

Raw/provenance tables (`crime_aggregate_fact.*`) remain available for auditing but should not be shown directly to end users.

## Grain

One row =

`year × geo_name × crime_category_normalized`

## Fields

| Field | Meaning |
|---|---|
| `year` | Calendar year of reported cases |
| `geo_name` | `Bengaluru City`, `Bengaluru District`, or `Bengaluru Railways` |
| `geo_level` | `city` or `district` |
| `crime_category_normalized` | Platform category (see list below) |
| `value` | Count of reported cases for that year/place/category |
| `metric` | Always `reported_cases` in canonical output |
| `quality_tier` | `A` high-trust official incidence; `B` solid open aggregate; `C` thin/partial |
| `completeness` | `category_detail`, `partial_detail`, or `total_only` |
| `detail_category_count` | How many non-total categories exist for that year/place |
| `confidence` | Pipeline confidence for selected source row (0-1) |
| `source_id` | Winning source family |
| `raw_file` | Winning source file |
| `source_labels` | Original labels rolled into this category |
| `user_note` | Plain-language caveat for UI |

## Categories published

- Total Crimes Against Women
- Sexual Assault
- Assault
- Domestic Violence
- Dowry Related
- Kidnapping
- Trafficking
- Eve Teasing
- Stalking
- Harassment
- Workplace Harassment
- Public Space Harassment
- Cyber Crime

## Source preference (simplified)

1. Bengaluru City Police / OpenCity women CSVs when available (recent city category + totals)
2. NCRB Table 5.1 / 3B.1 for 2012-2016 city totals and metro CAW tables
3. India Data Portal district CAW for 2017-2020 city/district/railways category detail (exclusive heads only)
4. Karnataka OpenCity district/city harassment tables as supporting detail when no city total pack exists

## Believability guards

- Statewide Karnataka review tables are **not** attributed to Bengaluru City
- IDP overlapping POCSO/subtype columns are excluded from category sums
- When an official Total exists for a year/place, only that source's categories are published
- Category packs where any head exceeds the Total are dropped (Total kept)

## Reference map layers (geography only)

Prepared into `web/data/geo/` for the Kavacha UI:

| Layer | File | Meaning |
|---|---|---|
| Police stations | `police_stations.geojson` | Bengaluru Urban station points (OpenCity KML) |
| Police jurisdictions | `police_jurisdictions.geojson` | Station boundary polygons |
| BBMP wards 2023 | `bbmp_wards_2023.geojson` | Final ward polygons |

Rebuild: `python scripts/prepare_map_layers.py`

**Rule:** never choropleth these polygons with city-level CAW totals. There is no official open ward/station crime count feed in this corpus.

## What this dataset is NOT

- Not street-level, ward-level, or police-station-level incident points
- Not victim-identifiable records
- Not a claim that every year has equal category detail
- Not a claim that category sums always equal the official Total (some heads may be unpublished)
- Not a safety score or heat map

## Current snapshot

- Canonical rows: **182**
- Years: **2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023**
- Geos: **Bengaluru City, Bengaluru District, Bengaluru Railways**
- Bengaluru City total years: **2012, 2013, 2014, 2015, 2016, 2021, 2022, 2023**
- Duplicate canonical keys: **0**
- City detail ≤ total check: **PASS**
