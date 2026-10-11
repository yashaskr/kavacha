# Source Inventory — Bengaluru Women's Safety (Online-first)

Living catalog of sources for building a longitudinal crimes-against-women dataset focused on Bengaluru. Machine-readable twin: [`catalogs/sources.yaml`](../catalogs/sources.yaml).

## Data reality

| Granularity | Online? | Notes |
|---|---|---|
| National / state / metro trends | Yes | NCRB Crime in India; metro city tables |
| District / Bengaluru City commissionerate | Yes | India Data Portal; OpenCity Karnataka CSVs |
| Crime-type breakdown (city) | Partial | OpenCity BCP women crime CSV 2021–2023 |
| Police-station / ward / street incidents | **No** | Not published as open geocoded FIRs |
| GIS reference | Yes | BBMP wards; police stations/jurisdictions |

## Tier A — direct online downloads

| Source | URL | Access | Format | Years | Geo | License | Update | Value |
|---|---|---|---|---|---|---|---|---|
| OpenCity Bengaluru Crime 2023 | https://data.opencity.in/dataset/bengaluru-crime-data-2023 | CKAN | CSV, PDF | 2021–2023 | Bengaluru City | Public Domain (OpenCity) | Annual | High |
| OpenCity Karnataka Crime 2022 | https://data.opencity.in/dataset/karnataka-crime-data-2022 | CKAN | CSV, PDF | 2022 | KA districts/cities | Public Domain | Annual | High |
| OpenCity Karnataka Crime 2023 | https://data.opencity.in/dataset/karnataka-crime-data-2023 | CKAN | CSV, PDF | 2023 | KA districts/cities | Public Domain | Annual | High |
| OpenCity Karnataka Crime 2024 | https://data.opencity.in/dataset/karnataka-crime-data-2024 | CKAN | CSV, PDF | 2024 | KA districts/cities | Public Domain | Annual | High |
| OpenCity Karnataka Crime 2025 | https://data.opencity.in/dataset/karnataka-crime-data-2025 | CKAN | CSV, PDF | 2025 | KA districts/cities | Public Domain | Annual | Medium |
| India Data Portal District CAW | https://ckandev.indiadataportal.com/dataset/crime-statistics/resource/c8d3ea7e-4855-45f3-9c26-557419e93b6a | HTTP CSV | CSV | 2017–2022 | India districts | Unspecified; from NCRB | Yearly | High |
| data.gov.in District CAW catalog | https://www.data.gov.in/catalog/district-wise-crimes-committed-against-women | Portal / API | CSV/ZIP | Historical (varies) | India districts | NDSAP | Irregular | Medium |
| OpenCity BBMP wards | https://data.opencity.in/dataset/bbmp-ward-information | CKAN | KML, CSV | 2015/2022/2023 | BBMP | Public Domain | After delimitation | High |
| OpenCity BBMP delimitation 2023 | https://data.opencity.in/dataset/bbmp-wards-delimitation-2023 | CKAN | KML, PDF | 2023 | 225 wards | Public Domain | After delimitation | High |
| OpenCity police station locations | https://data.opencity.in/dataset/police-station-locations | CKAN | KML | Point-in-time | KA / Bengaluru Urban | Public Domain; KSRSAC | Irregular | High |
| OpenCity police jurisdictions | https://data.opencity.in/dataset/police-jurisdiction-maps-for-major-cities-of-india | CKAN | KML/GeoJSON | Point-in-time | Major cities | Public Domain | Irregular | High |
| india-geodata KN police boundaries | https://github.com/yashveeeeeeer/india-geodata/releases/tag/police%2Fjurisdictions | GitHub release | Parquet, PMTiles | Point-in-time | Karnataka | See upstream | Irregular | High |

## Tier B — PDF / XLSX extraction (online, structured after parse)

| Source | URL | Access | Format | Years | Geo | License | Update | Value |
|---|---|---|---|---|---|---|---|---|
| NCRB Crime in India PDFs | https://ncrb.gov.in/crime-in-india.html | PDF download | PDF | 2012–present | India / metros / districts | GoI publication | Annual | High |
| NCRB CAW backfill 2012-2016 | https://www.ncrb.gov.in/crime-in-india-table-content.html | Chapter/table PDF + district XLSX | PDF, XLSX | 2012–2016 | Bengaluru City / District | GoI publication | One-time backfill | High |
| Crime in Karnataka PDFs | Via OpenCity / KSP packages | PDF | PDF | ~2022–2025 | Karnataka districts | Public Domain redistrib. | Annual | High |

Backfill command:

```bash
python -m src.cli collect --source ncrb_backfill
python -m src.cli normalize
python -m src.cli report
```

## Tier C — documented only (not collected in Phase 1)

| Source | Why deferred |
|---|---|
| Deccan Herald / ToI / Hindu / IE / Citizen Matters | Copyright/ToS; useful later for NLP geocoding only |
| eCourts / HC / district courts | PII risk; poor street-safety structure |
| Synthetic Kaggle geospatial “women safety” sets | **Exclude** from production corpus |

## Upstream origin sites (context)

- Bengaluru City Police: https://bcp.karnataka.gov.in
- Karnataka State Police: https://ksp.karnataka.gov.in
- NCRB: https://ncrb.gov.in
- Open Government Data Platform India: https://www.data.gov.in
- BBMP: municipal GIS via OpenCity mirrors

## Related research

Full external inventory + backlog notes: [`open_data_research.md`](open_data_research.md).

## How to refresh this inventory

1. Edit `catalogs/sources.yaml`
2. Re-run collectors: `python -m src.cli collect`
3. Regenerate coverage: `python -m src.cli report`
