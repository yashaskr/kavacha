# Coverage Report - Bengaluru Women's Safety Data

Generated: 2026-10-11T15:07:29.648176+00:00

## Summary

- Staged fact rows: **1162**
- Years present in staging: **2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023**
- Target window: **2012-2026**
- Years with data: **12 / 15**
- Reference GIS files discovered: **24**

## Critical gaps (spatial honesty)

- **No public open FIR / street-level / ward-level / police-station-level incident feed** was found online.
- Current corpus is **aggregate** (city / district / category / year).
- GIS layers (wards, police stations, jurisdictions) are collected as **reference**, not as crime counts.
- Years before ~2017 likely require **NCRB PDF table extraction** (Tier B) for district CAW backfill.

## Year coverage (2012 to present)

| Year | Status |
| --- | --- |
| 2012 | HAVE |
| 2013 | HAVE |
| 2014 | HAVE |
| 2015 | HAVE |
| 2016 | HAVE |
| 2017 | HAVE |
| 2018 | HAVE |
| 2019 | HAVE |
| 2020 | HAVE |
| 2021 | HAVE |
| 2022 | HAVE |
| 2023 | HAVE |
| 2024 | GAP |
| 2025 | GAP |
| 2026 | GAP |

## QC checks

| Check | Result | Detail |
| --- | --- | --- |
| non_empty_facts | PASS | 1162 fact rows |
| required_columns | PASS | all present |
| year_present | PASS | 0 rows missing year |
| numeric_values | PASS | 0 non-numeric values |
| year_range | PASS | 0 years outside 2000-2030 |
| duplicate_keys | PASS | 0 duplicate extras after key collapse |
| bengaluru_rows | PASS | 1162 Bengaluru-related rows |
| taxonomy_coverage | PASS | 18.8% mapped to Other |
| canonical_unique_keys | PASS | 0 duplicate canonical keys |
| canonical_city_detail_lte_total | PASS | 0 city years where category sum exceeds total |
| canonical_no_state_as_city | PASS | 0 implausible statewide-sized city rows |

## Geo levels in staging

| geo_level | rows |
| --- | --- |
| city | 842 |
| district | 320 |

## Normalized categories (top)

| crime_category_normalized | rows |
| --- | --- |
| Other | 219 |
| Sexual Assault | 206 |
| Trafficking | 188 |
| Assault | 142 |
| Kidnapping | 98 |
| Harassment | 62 |
| Cyber Crime | 54 |
| Dowry Related | 50 |
| Domestic Violence | 44 |
| Eve Teasing | 44 |
| Stalking | 16 |
| Workplace Harassment | 14 |
| Public Space Harassment | 14 |
| Total Crimes Against Women | 11 |

## Source inventory snapshot

| source_id | tier | years | geo | value |
| --- | --- | --- | --- | --- |
| opencity_bengaluru_crime_2023 | A | 2021-2023 | Bengaluru City | High |
| opencity_karnataka_crime_2022 | A | 2022 | Karnataka districts and cities | High |
| opencity_karnataka_crime_2023 | A | 2023 | Karnataka districts and cities | High |
| opencity_karnataka_crime_2024 | A | 2024 | Karnataka districts and cities | High |
| opencity_karnataka_crime_2025 | A | 2025 | Karnataka districts and cities | Medium |
| idp_district_caw_2017 | A | 2017-2022 | India districts (filter Karnataka / Bengaluru) | High |
| datagovin_district_caw_catalog | A | historical (varies by resource; often pre-2017) | India districts | Medium |
| opencity_bbmp_wards | A | 2015, 2022, 2023 | BBMP wards | High |
| opencity_bbmp_wards_2023 | A | 2023 | BBMP 225 wards | High |
| opencity_police_stations | A | point-in-time (may lag new stations) | Karnataka / Bengaluru Urban | High |
| opencity_police_jurisdictions | A | point-in-time | Major cities incl. Bengaluru | High |
| india_geodata_kn_police_boundaries | A | point-in-time | Karnataka | High |
| ncrb_crime_in_india_pdfs | B | 2012-present (annual) | India; metro cities and districts in tables | High |
| ncrb_caw_backfill_2012_2016 | B | 2012-2016 | Bengaluru/Bangalore city + district rows in CAW tables | High |
| media_archives | C | varies | Bengaluru | Medium (later NLP geocoding) |
| ecourts | C | varies | India | Low for street safety mapping |
| synthetic_kaggle_geospatial | C | n/a | synthetic metros | None for production corpus |

## Reference GIS samples

- `opencity_police_stations\2026-10-11\Bengaluru Urban Police Outpost Locations Map.kml`
- `opencity_police_stations\2026-10-11\Bengaluru Urban Police Station Locations.kml`
- `opencity_police_stations\2026-10-11\Bengaluru Urban Railway Police Stations Map.kml`
- `opencity_police_stations\2026-10-11\Karnataka Police Outpost Locations Map.kml`
- `opencity_police_stations\2026-10-11\Karnataka Police Station Locations Map.kml`
- `opencity_police_stations\2026-10-11\Karnataka Railway Police Stations Map.kml`
- `opencity_police_jurisdictions\2026-10-11\Bengaluru Police Jurisdictions Map.kml`
- `opencity_police_jurisdictions\2026-10-11\Hyderabad Police Jurisdictions Map.kml`
- `opencity_police_jurisdictions\2026-10-11\Mumbai Police Jurisdictions Map.kml`
- `opencity_bbmp_wards_2023\2026-10-11\BBMP Final Wards Map - 2023.kml`
- `opencity_bbmp_wards_2023\2026-10-11\BBMP Proposed Wards Map 2023.kml`
- `opencity_bbmp_wards\2026-10-11\BBMP Final Wards Map - 2023.kml`
- `opencity_bbmp_wards\2026-10-11\BBMP Proposed Wards 2023.kml`
- `opencity_bbmp_wards\2026-10-11\BBMP Ward Information.csv`
- `opencity_bbmp_wards\2026-10-11\BBMP Ward Map - 2015.kml`

## Manifest

```json
{
  "fact_rows": 1162,
  "sources": [
    "idp_district_caw_2017",
    "ncrb_caw_backfill_2012_2016",
    "opencity_bengaluru_crime_2023",
    "opencity_karnataka_crime_2022",
    "opencity_karnataka_crime_2023"
  ],
  "years": [
    2012,
    2013,
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023
  ],
  "geo_names": [
    "Bengaluru City",
    "Bengaluru District",
    "Bengaluru Railways"
  ],
  "parquet": "C:\\Users\\user\\Downloads\\women-safety-project\\data\\staging\\crime_aggregate_fact.parquet",
  "csv": "C:\\Users\\user\\Downloads\\women-safety-project\\data\\staging\\crime_aggregate_fact.csv",
  "reference_files": 86
}
```

## End-user canonical product

After `python -m src.cli clean`, prefer:

- `data/staging/crime_annual_bengaluru_city.csv`
- `data/staging/crime_annual_totals.csv`
- `docs/data_dictionary.md` / `docs/canonical_summary.md`

Do not show raw `crime_aggregate_fact` directly to end users.

## Recommended next decisions

1. Fill city **Total** gaps for 2017-2020 / 2024-2025 from official BCP or NCRB city tables when published.
2. Keep the map as **reference geography only** until official sub-city counts exist.
3. Only then consider safety scores — and separately, a clearly labeled news-derived event layer.
