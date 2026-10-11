"""Build end-user canonical annual crime tables.

Design goals:
- One believable number per year x place x category
- Prefer official BCP/NCRB incidence tables over noisy PDF extracts
- Exclude junk labels and non-count metrics from the public table
- Attach explicit quality flags so thin years are not oversold
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src.normalize.taxonomy import (
    IDP_PRIMARY_COLUMNS,
    PUBLISHABLE_CATEGORIES,
    is_drop_source_label,
    normalize_category,
)
from src.paths import STAGING, DOCS, ensure_data_dirs

logger = logging.getLogger(__name__)

# Higher is better
SOURCE_RANK = {
    "opencity_bengaluru_crime_2023": 100,  # BCP city women series
    "opencity_karnataka_crime_2022": 80,
    "opencity_karnataka_crime_2023": 80,
    "opencity_karnataka_crime_2024": 70,
    "opencity_karnataka_crime_2025": 70,
    "idp_district_caw_2017": 60,
    "ncrb_caw_backfill_2012_2016": 90,  # strong for 2012-2016 totals / metro tables
}

COUNT_METRICS = {"reported", "incidents", "value"}

# NCRB parent labels preferred over subtypes within a category
NCRB_PARENT_LABELS = {
    "Sexual Assault": ("rape (total)",),
    "Assault": ("assault on women (total)",),
}


def _source_rank(source_id: str, raw_file: str) -> int:
    base = SOURCE_RANK.get(str(source_id), 10)
    name = str(raw_file or "").lower()
    # Boost clean incidence tables
    if any(k in name for k in ("table_5_1", "table-5.1", "3b.1", "3b1", "crimes against women 2023")):
        base += 20
    # Category PDF extracts are often misaligned — demote vs totals tables
    if any(k in name for k in ("3b.2", "3b2", "table_5_2", "table-5.2")):
        base -= 30
    if "full publication" in name:
        base -= 50
    if name.startswith("col_"):
        base -= 100
    return base


def _load_facts() -> pd.DataFrame:
    parquet = STAGING / "crime_aggregate_fact.parquet"
    csv = STAGING / "crime_aggregate_fact.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv)
    return pd.DataFrame()


def _remap_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Re-apply latest taxonomy to source labels."""
    out = df.copy()
    cats = []
    confs = []
    for label in out["crime_category_source"].astype(str):
        cat, conf = normalize_category(label)
        cats.append(cat)
        confs.append(conf)
    out["crime_category_normalized"] = cats
    out["category_confidence"] = confs
    return out


def _filter_idp_primary(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only mutually exclusive IDP columns to avoid POCSO/rape double-counts."""
    if df.empty:
        return df
    keep: list[bool] = []
    for _, row in df.iterrows():
        if not str(row["source_id"]).startswith("idp_"):
            keep.append(True)
            continue
        label = str(row["crime_category_source"]).strip()
        mapped = IDP_PRIMARY_COLUMNS.get(label)
        keep.append(mapped is not None and mapped == row["crime_category_normalized"])
    return df.loc[keep].copy()


def _prepare_count_rows(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work = work[work["metric"].isin(COUNT_METRICS)].copy()
    work = work[~work["crime_category_source"].map(is_drop_source_label)].copy()
    work = work[pd.to_numeric(work["value"], errors="coerce").notna()].copy()
    work["value"] = pd.to_numeric(work["value"], errors="coerce")
    work = work[work["value"] >= 0].copy()
    work = _remap_categories(work)

    # Keep publishable categories only (drops low-value Other noise from public table)
    work = work[work["crime_category_normalized"].isin(PUBLISHABLE_CATEGORIES)].copy()
    work = _filter_idp_primary(work)

    # Normalize metric name for product
    work["metric"] = "reported_cases"
    raw_files = work["raw_file"] if "raw_file" in work.columns else pd.Series([""] * len(work))
    work["source_rank"] = [_source_rank(s, r) for s, r in zip(work["source_id"], raw_files)]
    return work


def _value_for_category_group(
    grp: pd.DataFrame, category: str, source_id: str
) -> tuple[float, list[str]]:
    """Aggregate labels inside one source/file/category without hierarchical double-counts."""
    per_label = grp.groupby("crime_category_source", as_index=False)["value"].max()
    labels = sorted(per_label["crime_category_source"].astype(str).tolist())

    if category == "Total Crimes Against Women":
        return float(per_label["value"].max()), labels

    # Prefer explicit parent totals in NCRB extracts when present
    if str(source_id).startswith("ncrb_"):
        parents = NCRB_PARENT_LABELS.get(category, ())
        parent_rows = per_label[
            per_label["crime_category_source"].astype(str).str.lower().isin(parents)
        ]
        if not parent_rows.empty:
            lab = parent_rows["crime_category_source"].astype(str).tolist()
            return float(parent_rows["value"].iloc[0]), lab
        totalish = per_label[
            per_label["crime_category_source"]
            .astype(str)
            .str.contains(r"\bTotal\b", case=False, na=False)
        ]
        if len(totalish) == 1:
            return (
                float(totalish["value"].iloc[0]),
                totalish["crime_category_source"].astype(str).tolist(),
            )

    return float(per_label["value"].sum()), labels


def _aggregate_within_source(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse subtype columns from the same source/file into one category value."""
    if df.empty:
        return df

    group_cols = [
        "year",
        "geo_name",
        "geo_level",
        "source_id",
        "raw_file",
        "crime_category_normalized",
    ]
    rows = []
    for keys, grp in df.groupby(group_cols, dropna=False):
        year, geo_name, geo_level, source_id, raw_file, category = keys
        value, labels = _value_for_category_group(grp, category, str(source_id))
        rows.append(
            {
                "year": int(year),
                "geo_name": geo_name,
                "geo_level": geo_level,
                "crime_category_normalized": category,
                "value": value,
                "metric": "reported_cases",
                "source_id": source_id,
                "raw_file": raw_file,
                "source_rank": int(grp["source_rank"].max()),
                "confidence": float(grp["confidence"].max()) if "confidence" in grp else 0.7,
                "category_confidence": float(grp["category_confidence"].max()),
                "source_labels": " | ".join(labels[:12]),
            }
        )
    return pd.DataFrame(rows)


def _drop_inconsistent_detail(df: pd.DataFrame) -> pd.DataFrame:
    """Drop category rows that cannot coexist with the same-source total.

    If any non-total category exceeds the Total for that year/geo/source/file,
    discard all non-total categories from that pack (keep the Total).
    """
    if df.empty:
        return df
    out_parts: list[pd.DataFrame] = []
    group_cols = ["year", "geo_name", "source_id", "raw_file"]
    for _, grp in df.groupby(group_cols, dropna=False):
        totals = grp[grp["crime_category_normalized"] == "Total Crimes Against Women"]
        detail = grp[grp["crime_category_normalized"] != "Total Crimes Against Women"]
        if totals.empty or detail.empty:
            out_parts.append(grp)
            continue
        total_val = float(totals["value"].max())
        detail_sum = float(detail["value"].sum())
        if (detail["value"] > total_val).any() or detail_sum > total_val + 1.0:
            logger.info(
                "Dropping inconsistent category detail for %s %s %s "
                "(detail_sum=%s total=%s)",
                grp["year"].iloc[0],
                grp["geo_name"].iloc[0],
                grp["raw_file"].iloc[0],
                int(detail_sum),
                int(total_val),
            )
            out_parts.append(totals)
        else:
            out_parts.append(grp)
    return pd.concat(out_parts, ignore_index=True) if out_parts else df


def _enforce_source_coherence(df: pd.DataFrame) -> pd.DataFrame:
    """When a trusted Total exists for year×geo, keep only that source's rows.

    Prevents mixing BCP totals with IDP/Karnataka fill-ins that inflate
    category sums above the official total.
    """
    if df.empty:
        return df
    preferred = (
        df[df["crime_category_normalized"] == "Total Crimes Against Women"]
        .sort_values(
            ["year", "geo_name", "source_rank", "confidence"],
            ascending=[True, True, False, False],
        )
        .drop_duplicates(subset=["year", "geo_name"], keep="first")
    )
    if preferred.empty:
        return df

    keep_keys = {
        (int(r.year), str(r.geo_name), str(r.source_id))
        for r in preferred.itertuples(index=False)
    }
    years_with_total = {
        (int(r.year), str(r.geo_name)) for r in preferred.itertuples(index=False)
    }

    mask = []
    for row in df.itertuples(index=False):
        key_yg = (int(row.year), str(row.geo_name))
        if key_yg in years_with_total:
            mask.append((int(row.year), str(row.geo_name), str(row.source_id)) in keep_keys)
        else:
            mask.append(True)
    return df.loc[mask].copy()


def _pick_best_source(df: pd.DataFrame) -> pd.DataFrame:
    """One row per year x geo x category using source rank."""
    if df.empty:
        return df
    ordered = df.sort_values(
        ["year", "geo_name", "crime_category_normalized", "source_rank", "confidence"],
        ascending=[True, True, True, False, False],
    )
    best = ordered.drop_duplicates(
        subset=["year", "geo_name", "crime_category_normalized"],
        keep="first",
    ).copy()
    return best


def _drop_year_inconsistent_detail(df: pd.DataFrame) -> pd.DataFrame:
    """Final guard: if published detail sum exceeds published Total, keep Total only.

    Catches cross-file mixes (e.g. NCRB 3B.1 total + broken 3B.2 categories).
    """
    if df.empty:
        return df
    parts: list[pd.DataFrame] = []
    for (year, geo), grp in df.groupby(["year", "geo_name"], dropna=False):
        totals = grp[grp["crime_category_normalized"] == "Total Crimes Against Women"]
        detail = grp[grp["crime_category_normalized"] != "Total Crimes Against Women"]
        if totals.empty or detail.empty:
            parts.append(grp)
            continue
        total_val = float(totals["value"].max())
        detail_sum = float(detail["value"].sum())
        if detail_sum > total_val + 1.0:
            logger.info(
                "Year-level drop of category detail for %s %s (detail_sum=%s total=%s)",
                year,
                geo,
                int(detail_sum),
                int(total_val),
            )
            parts.append(totals)
        else:
            parts.append(grp)
    return pd.concat(parts, ignore_index=True) if parts else df


def _quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # Completeness by year/geo: how many publishable categories present (excluding Total)
    detail_cats = [c for c in PUBLISHABLE_CATEGORIES if c != "Total Crimes Against Women"]
    counts = (
        out[out["crime_category_normalized"].isin(detail_cats)]
        .groupby(["year", "geo_name"])["crime_category_normalized"]
        .nunique()
        .rename("detail_category_count")
        .reset_index()
    )
    out = out.merge(counts, on=["year", "geo_name"], how="left")
    out["detail_category_count"] = out["detail_category_count"].fillna(0).astype(int)

    def _completeness(n: int) -> str:
        if n <= 0:
            return "total_only"
        if n < 4:
            return "partial_detail"
        return "category_detail"

    out["completeness"] = out["detail_category_count"].map(_completeness)

    def _tier(row: pd.Series) -> str:
        # A = high-trust official incidence; B = solid open aggregate; C = thin/partial
        if row["completeness"] == "total_only":
            return "C"
        if row["source_rank"] >= 90 and row["confidence"] >= 0.75:
            return "A"
        if row["source_rank"] >= 60 and row["confidence"] >= 0.65:
            return "B"
        return "C"

    out["quality_tier"] = out.apply(_tier, axis=1)

    out["user_note"] = out.apply(
        lambda r: (
            "Official annual total only; category breakdown not published for this year/place."
            if r["completeness"] == "total_only"
            else (
                "Partial category coverage for this year/place; compare with caution."
                if r["completeness"] == "partial_detail"
                else "Category breakdown available from official aggregate statistics."
            )
        ),
        axis=1,
    )
    return out


def build_canonical() -> dict:
    ensure_data_dirs()
    raw = _load_facts()
    if raw.empty:
        raise RuntimeError("No staged facts found. Run `python -m src.cli normalize` first.")

    prepared = _prepare_count_rows(raw)
    within = _aggregate_within_source(prepared)
    within = _drop_inconsistent_detail(within)
    coherent = _enforce_source_coherence(within)
    best = _pick_best_source(coherent)
    best = _drop_year_inconsistent_detail(best)
    canonical = _quality_flags(best)

    # Stable column order for product consumers
    cols = [
        "year",
        "geo_name",
        "geo_level",
        "crime_category_normalized",
        "value",
        "metric",
        "quality_tier",
        "completeness",
        "detail_category_count",
        "confidence",
        "category_confidence",
        "source_id",
        "raw_file",
        "source_labels",
        "user_note",
    ]
    for c in cols:
        if c not in canonical.columns:
            canonical[c] = None
    canonical = canonical[cols].sort_values(
        ["year", "geo_name", "crime_category_normalized"]
    ).reset_index(drop=True)

    # Dedicated totals series (most important end-user chart)
    totals = canonical[
        canonical["crime_category_normalized"] == "Total Crimes Against Women"
    ].copy()
    totals = totals.sort_values(["geo_name", "year"]).reset_index(drop=True)

    # City-first public slice (default product view)
    city = canonical[canonical["geo_name"] == "Bengaluru City"].copy()

    STAGING.mkdir(parents=True, exist_ok=True)
    paths = {
        "canonical": STAGING / "crime_annual_canonical.parquet",
        "canonical_csv": STAGING / "crime_annual_canonical.csv",
        "totals": STAGING / "crime_annual_totals.parquet",
        "totals_csv": STAGING / "crime_annual_totals.csv",
        "city": STAGING / "crime_annual_bengaluru_city.parquet",
        "city_csv": STAGING / "crime_annual_bengaluru_city.csv",
    }
    canonical.to_parquet(paths["canonical"], index=False)
    canonical.to_csv(paths["canonical_csv"], index=False)
    totals.to_parquet(paths["totals"], index=False)
    totals.to_csv(paths["totals_csv"], index=False)
    city.to_parquet(paths["city"], index=False)
    city.to_csv(paths["city_csv"], index=False)

    # QC summary for canonical
    city_detail_check = []
    for year, grp in city.groupby("year"):
        total_row = grp[grp.crime_category_normalized == "Total Crimes Against Women"]
        detail = grp[grp.crime_category_normalized != "Total Crimes Against Women"]
        total = float(total_row["value"].iloc[0]) if len(total_row) else None
        detail_sum = float(detail["value"].sum()) if len(detail) else 0.0
        city_detail_check.append(
            {
                "year": int(year),
                "total": total,
                "detail_sum": detail_sum,
                "detail_lte_total": (total is None) or (detail_sum <= total + 1e-6),
            }
        )

    qc = {
        "canonical_rows": int(len(canonical)),
        "years": sorted(int(y) for y in canonical["year"].dropna().unique()),
        "geo_names": sorted(canonical["geo_name"].dropna().unique().tolist()),
        "categories": sorted(canonical["crime_category_normalized"].dropna().unique().tolist()),
        "quality_tier_counts": canonical["quality_tier"].value_counts().to_dict(),
        "completeness_counts": canonical["completeness"].value_counts().to_dict(),
        "city_total_years": sorted(
            int(y) for y in totals.loc[totals["geo_name"] == "Bengaluru City", "year"].unique()
        ),
        "duplicate_keys": int(
            canonical.duplicated(
                subset=["year", "geo_name", "crime_category_normalized"], keep=False
            ).sum()
        ),
        "city_detail_vs_total": city_detail_check,
        "city_detail_ok": all(x["detail_lte_total"] for x in city_detail_check),
    }
    (STAGING / "canonical_qc.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")

    _write_data_dictionary(qc)
    _write_canonical_summary(canonical, totals, qc)

    logger.info(
        "Canonical built: %s rows, years %s, city_detail_ok=%s",
        qc["canonical_rows"],
        qc["years"],
        qc["city_detail_ok"],
    )
    return {
        "canonical_rows": qc["canonical_rows"],
        "years": qc["years"],
        "geo_names": qc["geo_names"],
        "quality_tier_counts": qc["quality_tier_counts"],
        "paths": {k: str(v) for k, v in paths.items()},
        "qc": qc,
    }


def _write_data_dictionary(qc: dict) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    text = f"""# Data Dictionary — Canonical Women's Crime Statistics (Bengaluru)

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

{chr(10).join('- ' + c for c in PUBLISHABLE_CATEGORIES)}

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

## What this dataset is NOT

- Not street-level, ward-level, or police-station-level incident points
- Not victim-identifiable records
- Not a claim that every year has equal category detail
- Not a claim that category sums always equal the official Total (some heads may be unpublished)

## Current snapshot

- Canonical rows: **{qc['canonical_rows']}**
- Years: **{', '.join(str(y) for y in qc['years'])}**
- Geos: **{', '.join(qc['geo_names'])}**
- Bengaluru City total years: **{', '.join(str(y) for y in qc['city_total_years'])}**
- Duplicate canonical keys: **{qc['duplicate_keys']}**
- City detail ≤ total check: **{'PASS' if qc.get('city_detail_ok') else 'FAIL'}**
"""
    (DOCS / "data_dictionary.md").write_text(text, encoding="utf-8")


def _write_canonical_summary(canonical: pd.DataFrame, totals: pd.DataFrame, qc: dict) -> None:
    city_totals = totals[totals["geo_name"] == "Bengaluru City"].sort_values("year")
    city = canonical[canonical["geo_name"] == "Bengaluru City"]
    lines = [
        "# Canonical Dataset Summary",
        "",
        "End-user-ready annual aggregates after cleaning.",
        "",
        "## Snapshot",
        "",
        f"- Rows: **{qc['canonical_rows']}**",
        f"- Years: **{', '.join(str(y) for y in qc['years'])}**",
        f"- Quality tiers: `{qc['quality_tier_counts']}`",
        f"- Completeness: `{qc['completeness_counts']}`",
        f"- City detail ≤ total: **{'PASS' if qc.get('city_detail_ok') else 'FAIL'}**",
        "",
        "## Bengaluru City annual totals",
        "",
        "| Year | Reported cases | Tier | Completeness | Source |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for _, r in city_totals.iterrows():
        lines.append(
            f"| {int(r['year'])} | {int(r['value'])} | {r['quality_tier']} | {r['completeness']} | {r['source_id']} |"
        )

    lines.extend(
        [
            "",
            "## Bengaluru City coverage by year",
            "",
            "| Year | Categories | Has total | Detail sum |",
            "| --- | ---: | --- | ---: |",
        ]
    )
    for item in qc.get("city_detail_vs_total", []):
        y = item["year"]
        n_cats = int(
            city.loc[city["year"] == y, "crime_category_normalized"].nunique()
        )
        has_total = "yes" if item["total"] is not None else "no"
        total_s = "" if item["total"] is None else str(int(item["total"]))
        lines.append(
            f"| {y} | {n_cats} | {has_total}{(' ('+total_s+')') if total_s else ''} | {int(item['detail_sum'])} |"
        )

    lines.extend(
        [
            "",
            "## Believability rules applied",
            "",
            "1. Only count metrics (`reported` / `incidents`) enter the product table.",
            "2. Junk labels (`col_*`, indexes, subtotals) dropped.",
            "3. Taxonomy remapped (SH subtypes, Voyeurism, Insult to modesty, etc.).",
            "4. IDP uses exclusive primary columns only (no overlapping POCSO/rape heads).",
            "5. Broken NCRB category packs where a head exceeds Total are dropped.",
            "6. When a year has an official Total, only that source's categories are shown.",
            "7. Statewide Karnataka tables are never labeled as Bengaluru City.",
            "8. Thin years flagged `total_only` / tier `C` so UI can avoid overclaiming.",
            "",
            "See also: [data_dictionary.md](data_dictionary.md)",
            "",
        ]
    )
    (DOCS / "canonical_summary.md").write_text("\n".join(lines), encoding="utf-8")
