# Tech stack & cost estimate — Bengaluru first

Planning ranges from research (Oct 2026). FX ~₹90–95/USD. Exclude GST; treat as ±30%.

Source: [Tech stack cost research](7349d9a4-bd41-44ab-ade5-52a20b7c9596)

## Current project position

This repo is already on the **data-first MVP path**: Python collect → normalize → clean, static **Kavacha** UI, OpenCity KML → GeoJSON reference map. No Docker/MinIO/Prefect required until you need scheduled refresh, multi-user hosting, or a public URL.

## Recommended stacks

| Layer | A) MVP — Docker Compose | B) Production — managed (prefer AWS Mumbai) |
| --- | --- | --- |
| Object / data lake | MinIO (S3 API) | S3 (or GCS); Glacier/IA for cold PDFs |
| Warehouse | Postgres 16 + PostGIS + pgvector | RDS Postgres + PostGIS (+ pgvector) |
| ETL | Python (pandas/polars, pdfplumber, GeoPandas) | Same; workers on ECS/Fargate or Cloud Run |
| Orchestration | Prefect OSS (or cron for 3–5 flows) | Prefect Cloud Hobby→Starter or self-hosted worker |
| API / frontend | Next.js + MapLibre GL | Same + CloudFront / Amplify / Vercel |
| Map tiles | MapLibre + Protomaps PMTiles | PMTiles on S3/R2 + CDN |
| Geocoding | Ward/polygon join first; skip public Nominatim | LocationIQ / OpenCage for UX search later |
| Vector / AI | pgvector + cheap LLM over **aggregates** | Same until scale |

**Avoid Airflow** for one-city MVP. Prefer Prefect (or Dagster if asset lineage is the mental model).

## Profile A — Compose MVP (~$55–100/mo · ₹5k–9.5k)

Target host: **Lightsail Mumbai or DO Bangalore, 8 GB**.

Suggested services: `minio` → `postgres(postgis+pgvector)` → `prefect` → `nextjs` (optional Redis).

| Item | Typical |
| --- | --- |
| VPS 8 GB | $44–48 |
| Backups / snapshots | $5–10 |
| Domain + Cloudflare | $0–2 |
| PMTiles | $0 (on-disk) |
| Optional geocoder / LLM | $0–35 |
| **Total** | **~$55–100** |

Defer self-hosted Nominatim to a **second** 16 GB+ box if bulk reverse-geocode ever justifies it.

## Profile B — Managed prod (~$180–400/mo · ₹17k–38k)

S3 + RDS PostGIS + app compute + CDN. Add Prefect Cloud, paid geocoder, Multi-AZ as SLA needs grow. HA / multi-city: plan **$500–800+/mo**.

## Concrete path from *this* repo

1. Keep shipping on local/static Kavacha + canonical CSVs until a partner needs always-on hosting.
2. When hosting: Compose on 8 GB IN VPS; keep bucket layout `raw/` · `staging/` · `curated/` (S3-compatible).
3. Load wards/jurisdictions/stations into **PostGIS**; keep the rule: **no choropleth of city totals onto wards**.
4. AI Q&A only over curated aggregate marts + methodology docs (pgvector), not raw incident text.
5. Safety scores / news layers only after explicit product rules — not implied by the reference map.

## Cost at a glance

| Profile | USD / month | INR / month | Best for |
| --- | --- | --- | --- |
| A MVP Compose (8 GB IN) | $55–100 | ₹5k–9.5k | Pilot, one city |
| B Lean managed | $150–220 | ₹14k–21k | Soft public launch |
| B Solid managed | $300–450 | ₹27k–43k | SLA + light AI |
| B HA / multi-city | $500–800+ | ₹45k–75k+ | Scale-out cities |

Verify live vendor prices before budgeting.
