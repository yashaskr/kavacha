"""Data quality checks on staged aggregates."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd

from src.paths import STAGING


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    count: int = 0


def load_facts() -> pd.DataFrame:
    parquet = STAGING / "crime_aggregate_fact.parquet"
    csv = STAGING / "crime_aggregate_fact.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv)
    return pd.DataFrame()


def run_checks(df: pd.DataFrame | None = None) -> list[CheckResult]:
    if df is None:
        df = load_facts()
    results: list[CheckResult] = []

    results.append(
        CheckResult(
            "non_empty_facts",
            ok=len(df) > 0,
            detail=f"{len(df)} fact rows",
            count=len(df),
        )
    )
    if df.empty:
        return results

    # Required columns
    required = [
        "geo_name",
        "year",
        "crime_category_source",
        "crime_category_normalized",
        "metric",
        "value",
        "source_id",
    ]
    missing = [c for c in required if c not in df.columns]
    results.append(
        CheckResult(
            "required_columns",
            ok=len(missing) == 0,
            detail="missing: " + ", ".join(missing) if missing else "all present",
            count=len(missing),
        )
    )

    null_years = int(df["year"].isna().sum()) if "year" in df.columns else len(df)
    results.append(
        CheckResult(
            "year_present",
            ok=null_years == 0,
            detail=f"{null_years} rows missing year",
            count=null_years,
        )
    )

    bad_values = int((~pd.to_numeric(df["value"], errors="coerce").notna()).sum())
    results.append(
        CheckResult(
            "numeric_values",
            ok=bad_values == 0,
            detail=f"{bad_values} non-numeric values",
            count=bad_values,
        )
    )

    # Impossible years
    years = pd.to_numeric(df["year"], errors="coerce")
    bad_years = int(((years < 2000) | (years > 2030)).sum())
    results.append(
        CheckResult(
            "year_range",
            ok=bad_years == 0,
            detail=f"{bad_years} years outside 2000-2030",
            count=bad_years,
        )
    )

    # Duplicate aggregate keys (count extras only)
    key = [
        "geo_name",
        "year",
        "crime_category_source",
        "metric",
        "source_id",
        "raw_file",
        "registration_circle",
    ]
    key = [c for c in key if c in df.columns]
    extras = int(df.duplicated(subset=key, keep="first").sum()) if key else 0
    results.append(
        CheckResult(
            "duplicate_keys",
            ok=extras == 0,
            detail=f"{extras} duplicate extras after key collapse",
            count=extras,
        )
    )

    # Bengaluru geo presence
    geo = df["geo_name"].astype(str) if "geo_name" in df.columns else pd.Series(dtype=str)
    beng = int(geo.str.contains("Bengaluru|Bangalore", case=False, na=False).sum())
    results.append(
        CheckResult(
            "bengaluru_rows",
            ok=beng > 0,
            detail=f"{beng} Bengaluru-related rows",
            count=beng,
        )
    )

    # Category mapping coverage
    other_share = float((df["crime_category_normalized"] == "Other").mean()) if len(df) else 1.0
    results.append(
        CheckResult(
            "taxonomy_coverage",
            ok=other_share < 0.6,
            detail=f"{other_share:.1%} mapped to Other",
            count=int(other_share * 100),
        )
    )

    # Canonical product checks (when clean has been run)
    canon_path = STAGING / "crime_annual_canonical.csv"
    if canon_path.exists():
        canon = pd.read_csv(canon_path)
        dup = int(
            canon.duplicated(
                subset=["year", "geo_name", "crime_category_normalized"], keep=False
            ).sum()
        )
        results.append(
            CheckResult(
                "canonical_unique_keys",
                ok=dup == 0,
                detail=f"{dup} duplicate canonical keys",
                count=dup,
            )
        )
        city = canon[canon["geo_name"] == "Bengaluru City"]
        bad_years = 0
        for _, grp in city.groupby("year"):
            totals = grp[grp["crime_category_normalized"] == "Total Crimes Against Women"]
            detail = grp[grp["crime_category_normalized"] != "Total Crimes Against Women"]
            if totals.empty or detail.empty:
                continue
            if float(detail["value"].sum()) > float(totals["value"].iloc[0]) + 1.0:
                bad_years += 1
        results.append(
            CheckResult(
                "canonical_city_detail_lte_total",
                ok=bad_years == 0,
                detail=f"{bad_years} city years where category sum exceeds total",
                count=bad_years,
            )
        )
        # Statewide Karnataka magnitudes must not appear as city Assault/Cyber
        inflated = city[
            (city["year"].isin([2024, 2025]))
            & (city["crime_category_normalized"].isin(["Assault", "Cyber Crime"]))
            & (city["value"] > 2000)
        ]
        results.append(
            CheckResult(
                "canonical_no_state_as_city",
                ok=len(inflated) == 0,
                detail=f"{len(inflated)} implausible statewide-sized city rows",
                count=len(inflated),
            )
        )

    return results


def checks_as_dicts(results: list[CheckResult]) -> list[dict]:
    return [asdict(r) for r in results]