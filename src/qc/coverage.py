"""Generate coverage / gap report for 2012–present."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.catalog import load_sources
from src.paths import DOCS, REFERENCE, STAGING, ensure_data_dirs
from src.qc.checks import load_facts, run_checks


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def generate_coverage_report() -> Path:
    ensure_data_dirs()
    df = load_facts()
    checks = run_checks(df)
    catalog = load_sources()
    sources = catalog.get("sources", [])

    current_year = datetime.now(timezone.utc).year
    target_years = list(range(2012, current_year + 1))

    present_years: set[int] = set()
    if not df.empty and "year" in df.columns:
        present_years = {int(y) for y in df["year"].dropna().unique()}

    year_rows = []
    for y in target_years:
        status = "HAVE" if y in present_years else "GAP"
        year_rows.append([str(y), status])

    geo_levels = []
    if not df.empty and "geo_level" in df.columns:
        for level, count in df["geo_level"].value_counts(dropna=False).items():
            geo_levels.append([str(level), str(int(count))])

    categories = []
    if not df.empty and "crime_category_normalized" in df.columns:
        for cat, count in df["crime_category_normalized"].value_counts().head(30).items():
            categories.append([str(cat), str(int(count))])

    source_rows = []
    for s in sources:
        source_rows.append(
            [
                str(s.get("id")),
                str(s.get("tier")),
                str(s.get("year_coverage", "")),
                str(s.get("geographic_coverage", "")).replace("|", "/"),
                str(s.get("estimated_value", "")),
            ]
        )

    check_rows = [
        [c.name, "PASS" if c.ok else "FAIL", c.detail.replace("|", "/")] for c in checks
    ]

    ref_count = 0
    ref_examples: list[str] = []
    if REFERENCE.exists():
        for path in REFERENCE.rglob("*"):
            if path.is_file() and path.suffix.lower() in {
                ".kml",
                ".kmz",
                ".geojson",
                ".parquet",
                ".pmtiles",
                ".csv",
            }:
                ref_count += 1
                if len(ref_examples) < 15:
                    ref_examples.append(str(path.relative_to(REFERENCE)))

    manifest = {}
    manifest_path = STAGING / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    lines = [
        "# Coverage Report - Bengaluru Women's Safety Data",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        f"- Staged fact rows: **{len(df)}**",
        f"- Years present in staging: **{', '.join(str(y) for y in sorted(present_years)) or 'none'}**",
        f"- Target window: **2012-{current_year}**",
        f"- Years with data: **{len(present_years & set(target_years))} / {len(target_years)}**",
        f"- Reference GIS files discovered: **{ref_count}**",
        "",
        "## Critical gaps (spatial honesty)",
        "",
        "- **No public open FIR / street-level / ward-level / police-station-level incident feed** was found online.",
        "- Current corpus is **aggregate** (city / district / category / year).",
        "- GIS layers (wards, police stations, jurisdictions) are collected as **reference**, not as crime counts.",
        "- Years before ~2017 likely require **NCRB PDF table extraction** (Tier B) for district CAW backfill.",
        "",
        "## Year coverage (2012 to present)",
        "",
        _md_table(["Year", "Status"], year_rows),
        "",
        "## QC checks",
        "",
        _md_table(["Check", "Result", "Detail"], check_rows),
        "",
        "## Geo levels in staging",
        "",
        _md_table(["geo_level", "rows"], geo_levels or [["(none)", "0"]]),
        "",
        "## Normalized categories (top)",
        "",
        _md_table(["crime_category_normalized", "rows"], categories or [["(none)", "0"]]),
        "",
        "## Source inventory snapshot",
        "",
        _md_table(
            ["source_id", "tier", "years", "geo", "value"],
            source_rows,
        ),
        "",
        "## Reference GIS samples",
        "",
    ]
    if ref_examples:
        lines.extend([f"- `{p}`" for p in ref_examples])
    else:
        lines.append("- _(none yet — run `python -m src.cli collect`)_")

    lines.extend(
        [
            "",
            "## Manifest",
            "",
            "```json",
            json.dumps(manifest, indent=2),
            "```",
            "",
        "## End-user canonical product",
        "",
        "After `python -m src.cli clean`, prefer:",
        "",
        "- `data/staging/crime_annual_bengaluru_city.csv`",
        "- `data/staging/crime_annual_totals.csv`",
        "- `docs/data_dictionary.md` / `docs/canonical_summary.md`",
        "",
        "Do not show raw `crime_aggregate_fact` directly to end users.",
        "",
        "## Recommended next decisions",
        "",
        "1. Fill city **Total** gaps for 2017-2020 / 2024-2025 from official BCP or NCRB city tables when published.",
        "2. Decide whether to pursue a **news-derived event layer** (lower confidence) for sub-city geography.",
        "3. Only then design map UI / safety scores on top of known resolutions.",
        "",
    ]
    )

    out = DOCS / "coverage_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")

    # Also dump machine-readable QC
    qc_path = STAGING / "qc_results.json"
    qc_path.write_text(
        json.dumps(
            {
                "checks": [c.__dict__ for c in checks],
                "years_present": sorted(present_years),
                "years_gap": [y for y in target_years if y not in present_years],
                "fact_rows": len(df),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return out