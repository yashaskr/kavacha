"""Build staged aggregate facts from raw downloads."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from src.catalog import source_by_id
from src.normalize.geo import alias_table_rows
from src.normalize.ncrb_extract import extract_backfill_dir, extract_from_pdf_text
from src.normalize.parsers import (
    iter_csv_files,
    parse_idp_district_caw,
    parse_opencity_district_total_csv,
    parse_opencity_wide_year_csv,
    year_from_source_id,
)
from src.normalize.taxonomy import taxonomy_rows
from src.paths import RAW, REFERENCE, STAGING, ensure_data_dirs

logger = logging.getLogger(__name__)

FACT_COLUMNS = [
    "geo_level",
    "geo_name",
    "geo_code",
    "year",
    "month",
    "crime_category_source",
    "crime_category_normalized",
    "metric",
    "value",
    "source_id",
    "source_url",
    "retrieved_at",
    "confidence",
    "category_confidence",
    "raw_file",
    "source_district",
    "registration_circle",
]


def _source_url(source_id: str) -> str | None:
    meta = source_by_id(source_id)
    return meta.get("url") if meta else None


def _latest_run_dirs(root: Path) -> list[tuple[str, Path]]:
    """Return (source_id, latest_dated_dir) for each source under root."""
    if not root.exists():
        return []
    out: list[tuple[str, Path]] = []
    for source_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        dated = sorted(p for p in source_dir.iterdir() if p.is_dir())
        if dated:
            out.append((source_dir.name, dated[-1]))
    return out


def _is_women_relevant_csv(path: Path) -> bool:
    name = path.name.lower()
    if any(x in name for x in ("accident", "suicide", "road accident", "children only")):
        # Allow combined women+children files; block pure accident/suicide extracts
        if "women" not in name:
            return False
    if "women" in name or "harass" in name or "sexual" in name:
        return True
    if "crime against" in name:
        return True
    return False


def _parse_source_dir(source_id: str, run_dir: Path) -> list[dict]:
    url = _source_url(source_id)
    facts: list[dict] = []

    # NCRB CAW backfill (PDF/XLSX years 2012-2016)
    if source_id.startswith("ncrb_caw_backfill"):
        facts.extend(extract_backfill_dir(run_dir, source_id=source_id, source_url=url or ""))
        # Also mine previously downloaded full 2016 publication (once)
        for other_id, other_dir in _latest_run_dirs(RAW):
            if other_id != "ncrb_crime_in_india_pdfs":
                continue
            facts.extend(
                extract_backfill_dir(
                    other_dir,
                    source_id=source_id,
                    source_url=url or "",
                )
            )
        return facts
    if source_id == "ncrb_crime_in_india_pdfs":
        # Skip here when dedicated backfill source exists (avoids double full-PDF parse)
        if any(sid.startswith("ncrb_caw_backfill") for sid, _ in _latest_run_dirs(RAW)):
            return []
        return extract_backfill_dir(run_dir, source_id=source_id, source_url=url or "")

    csvs = list(iter_csv_files(run_dir))
    if not csvs:
        return facts

    if source_id.startswith("idp_"):
        for path in csvs:
            facts.extend(parse_idp_district_caw(path, source_id=source_id, source_url=url))
        return facts

    if "bengaluru_crime" in source_id:
        for path in csvs:
            if not _is_women_relevant_csv(path):
                continue
            rows = parse_opencity_wide_year_csv(
                path,
                source_id=source_id,
                source_url=url,
                default_geo_name="Bengaluru City",
                default_geo_level="city",
                bengaluru_only=False,
            )
            for f in rows:
                f["confidence"] = max(float(f.get("confidence") or 0), 0.9)
            facts.extend(rows)
        return facts

    if source_id.startswith("opencity_karnataka"):
        year_hint = year_from_source_id(source_id)
        for path in csvs:
            name_l = path.name.lower()
            if not (_is_women_relevant_csv(path) or "harass" in name_l):
                continue
            # Statewide CAW review tables have no district column — do NOT
            # attribute them to Bengaluru City (values are Karnataka totals).
            statewide = any(
                k in name_l
                for k in (
                    "crimes against women children",
                    "crimes against women_children",
                    "crime review",
                    "ipc crimes under various",
                    "sll crimes under various",
                    "ipc and bns",
                )
            )
            # District/unit-wise tables (e.g. sexual harassment by city)
            district_rows = parse_opencity_district_total_csv(
                path,
                source_id=source_id,
                source_url=url,
                year_hint=year_hint,
            )
            if district_rows:
                facts.extend(district_rows)
                continue
            if statewide:
                logger.info(
                    "Skipping statewide (non-city) Karnataka table for city facts: %s",
                    path.name,
                )
                continue
            facts.extend(
                parse_opencity_wide_year_csv(
                    path,
                    source_id=source_id,
                    source_url=url,
                    default_geo_name="Bengaluru City",
                    default_geo_level="city",
                    bengaluru_only=True,
                )
            )
        return facts

    # Generic CSV attempt for other raw sources (women-relevant only)
    for path in csvs:
        if not _is_women_relevant_csv(path):
            continue
        facts.extend(
            parse_opencity_wide_year_csv(
                path,
                source_id=source_id,
                source_url=url,
                bengaluru_only=True,
            )
        )
        if not facts:
            facts.extend(
                parse_opencity_district_total_csv(
                    path,
                    source_id=source_id,
                    source_url=url,
                    year_hint=year_from_source_id(source_id),
                )
            )
    return facts


def build_staging() -> dict:
    ensure_data_dirs()
    all_facts: list[dict] = []

    for source_id, run_dir in _latest_run_dirs(RAW):
        logger.info("Normalizing %s from %s", source_id, run_dir)
        try:
            rows = _parse_source_dir(source_id, run_dir)
            logger.info("  -> %s fact rows", len(rows))
            all_facts.extend(rows)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Normalize failed for %s: %s", source_id, exc)

    df = pd.DataFrame(all_facts)
    if df.empty:
        df = pd.DataFrame(columns=FACT_COLUMNS)
    else:
        # Deduplicate identical aggregate keys
        key_cols = [
            "geo_level",
            "geo_name",
            "year",
            "month",
            "crime_category_source",
            "metric",
            "source_id",
            "raw_file",
            "registration_circle",
        ]
        for c in key_cols:
            if c not in df.columns:
                df[c] = None
        df = df.drop_duplicates(subset=key_cols, keep="last")

        # Collapse competing NCRB "Total CAW" values for same year/geo
        if {"crime_category_normalized", "metric", "raw_file", "confidence"}.issubset(df.columns):
            is_total = (df["crime_category_normalized"] == "Total Crimes Against Women") & (
                df["metric"].isin(["reported", "incidents", "value"])
            )
            totals = df[is_total].copy()
            others = df[~is_total].copy()
            if not totals.empty:
                def _pref(name: str) -> int:
                    n = str(name).lower()
                    if "table_5_1" in n or "table-5.1" in n or "3b.1" in n or "3b1" in n:
                        return 3
                    if "district_caw" in n or "ncr_caw" in n or "caw_chapter" in n:
                        return 2
                    if "full publication" in n:
                        return 0
                    return 1

                totals["_pref"] = totals["raw_file"].map(_pref)
                totals = totals.sort_values(["_pref", "confidence"], ascending=[False, False])
                totals = totals.drop_duplicates(subset=["year", "geo_name"], keep="first")
                totals = totals.drop(columns=["_pref"])
                df = pd.concat([others, totals], ignore_index=True)

        df = df.reindex(columns=[c for c in FACT_COLUMNS if c in df.columns] + [
            c for c in df.columns if c not in FACT_COLUMNS
        ])

    STAGING.mkdir(parents=True, exist_ok=True)
    parquet_path = STAGING / "crime_aggregate_fact.parquet"
    csv_path = STAGING / "crime_aggregate_fact.csv"
    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)

    tax = pd.DataFrame(taxonomy_rows())
    tax.to_csv(STAGING / "dim_crime_taxonomy.csv", index=False)

    aliases = pd.DataFrame(alias_table_rows())
    aliases.to_csv(STAGING / "dim_geo_bengaluru.csv", index=False)

    # Reference inventory (file list only — GIS stays in data/reference)
    ref_files = []
    if REFERENCE.exists():
        for path in REFERENCE.rglob("*"):
            if path.is_file() and path.name not in {"lineage.jsonl", "package_show.json"}:
                ref_files.append(
                    {
                        "path": str(path.relative_to(REFERENCE)),
                        "bytes": path.stat().st_size,
                        "suffix": path.suffix.lower(),
                    }
                )
    ref_df = pd.DataFrame(ref_files)
    ref_df.to_csv(STAGING / "reference_inventory.csv", index=False)

    manifest = {
        "fact_rows": int(len(df)),
        "sources": sorted(df["source_id"].dropna().unique().tolist()) if len(df) else [],
        "years": sorted([int(y) for y in df["year"].dropna().unique().tolist()]) if len(df) else [],
        "geo_names": sorted(df["geo_name"].dropna().unique().tolist()) if len(df) else [],
        "parquet": str(parquet_path),
        "csv": str(csv_path),
        "reference_files": len(ref_files),
    }
    (STAGING / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest