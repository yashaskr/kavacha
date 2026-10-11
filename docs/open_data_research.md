# Open crime data research — Bengaluru / Karnataka / India

External research inventory (Oct 2026). Living collect catalog remains [`source_inventory.md`](source_inventory.md) / [`catalogs/sources.yaml`](../catalogs/sources.yaml).

Source: [Crime data sources research](c8b02eab-adb2-4949-b5b0-38916eb633dc)

## Reality check

India does **not** publish US-style open, geocoded FIR APIs. CCTNS / Digital Police is authorized-use only. Public analysis is almost entirely **aggregate** counts (state → district/commissionerate → metro city), often PDF, sometimes CSV via OpenCity / Dataful.

**Street-level official crime points are not MVP-viable.** Viable product: city/district time series + ward/jurisdiction **reference** GIS + optional later crowdsourced/proxy layers (clearly labeled).

## Alignment with this repo

| Research recommendation | Status here |
| --- | --- |
| NCRB metro CAW for Bengaluru (incl. 2012–2016 backfill) | **Done** — `ncrb_caw_backfill_2012_2016` + canonical totals |
| OpenCity BCP CAW 2021–2023 | **Done** — city category + totals (tier A) |
| IDP / district CAW 2017+ | **Done** — exclusive-head categories for 2017–2020 |
| Karnataka SCRB / Crime Review via OpenCity | **Partial** — collected; statewide tables not attributed as city |
| BBMP wards + police jurisdictions + PS points | **Done** — reference map in Kavacha (`web/data/geo/`) |
| Canonical one-number-per-year×place×category | **Done** — `python -m src.cli clean` |
| Dataful NCRB metro tidy extracts | **Not collected** — optional ETL convenience; verify ToS |
| GBA 2025 ward delimitation | **Not collected** — next GIS refresh candidate |
| Safecity partnership | **Deferred** — crowdsourced, not FIR; request access |
| Kaggle “Karnataka FIR + lat/lon” dumps | **Avoid** — provenance/legal risk |
| Safety scores / news NLP geocoding | **Deferred** — needs explicit product rules |

## What does not exist publicly

- Open incident-level FIR API with lat/lon
- Official ward- or beat-level CAW time series
- Stable public CCTNS research extract
- CompStat-style daily crime points

Finest realistic official spatial join: **police-station jurisdiction polygons** + **city/commissionerate CAW totals** (not points). Never invent street dots from aggregates.

## Prioritized backlog (beyond current corpus)

1. **Fill city Total gaps** — 2017–2020 and 2024–2025 from BCP/NCRB metro tables when published (do not sum categories into a fake total).
2. **GBA / BBMP 2025 wards** — [OpenCity GBA delimitation](https://data.opencity.in/dataset/gba-wards-delimitation-2025) for current basemap (keep 2023 layer for historical join).
3. **Dataful metro CAW** (optional) — tidy NCRB mirrors for faster refresh; always reconcile to official PDFs.
4. **Safecity** — partnership only; separate layer labeled crowdsourced harassment, never mixed into FIR totals.
5. **RTI path** (aspirational) — PS-wise CAW aggregates from BCP/SCRB if released.

## Product rule (unchanged)

Join crime to maps **only** at grains you actually have (usually city). Reference GIS in Kavacha must stay non-choropleth until official sub-city counts exist.
