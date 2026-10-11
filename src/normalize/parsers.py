"""Parsers that turn raw downloads into aggregate fact rows."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.http_util import utc_now_iso
from src.normalize.geo import is_bengaluru_related, resolve_geo
from src.normalize.taxonomy import normalize_category

logger = logging.getLogger(__name__)

YEAR_COL_RE = re.compile(r"^(20\d{2})(?:\s*[-_]?\s*(reported|detected|cases?))?$", re.I)


def _clean_number(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip().replace(",", "")
    if text in {"", "-", "NA", "N/A", "na", "*"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _fact(
    *,
    geo_level: str | None,
    geo_name: str | None,
    geo_code: str | None,
    year: int | None,
    month: int | None,
    crime_category_source: str,
    metric: str,
    value: float,
    source_id: str,
    source_url: str | None,
    confidence: float,
    extra: dict | None = None,
) -> dict[str, Any]:
    cat, cat_conf = normalize_category(crime_category_source)
    row = {
        "geo_level": geo_level,
        "geo_name": geo_name,
        "geo_code": geo_code,
        "year": year,
        "month": month,
        "crime_category_source": crime_category_source,
        "crime_category_normalized": cat,
        "metric": metric,
        "value": value,
        "source_id": source_id,
        "source_url": source_url,
        "retrieved_at": utc_now_iso(),
        "confidence": min(confidence, cat_conf) if confidence else cat_conf,
        "category_confidence": cat_conf,
    }
    if extra:
        row.update(extra)
    return row


def parse_opencity_wide_year_csv(
    path: Path,
    *,
    source_id: str,
    source_url: str | None,
    default_geo_name: str = "Bengaluru City",
    default_geo_level: str = "city",
    bengaluru_only: bool = True,
) -> list[dict[str, Any]]:
    """Parse OpenCity-style CSVs with Type of Crime + year Reported/Detected columns."""
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read %s: %s", path, exc)
        return []

    if df.empty:
        return []

    cols = {c: str(c).strip() for c in df.columns}
    df = df.rename(columns=cols)
    # Find category column
    cat_col = None
    for candidate in df.columns:
        cl = candidate.lower()
        if "type" in cl or "crime" in cl or "category" in cl or "head" in cl:
            cat_col = candidate
            break
    if cat_col is None:
        cat_col = df.columns[0]

    geo_col = None
    for candidate in df.columns:
        cl = candidate.lower()
        if any(k in cl for k in ("district", "city", "unit", "commissionerate", "geo")):
            geo_col = candidate
            break

    facts: list[dict[str, Any]] = []
    for _, series in df.iterrows():
        category = series.get(cat_col)
        if pd.isna(category) or str(category).strip() == "":
            continue
        geo_name = default_geo_name
        geo_level = default_geo_level
        geo_conf = 0.9
        if geo_col is not None and not pd.isna(series.get(geo_col)):
            geo_raw = str(series.get(geo_col))
            if bengaluru_only and not is_bengaluru_related(geo_raw):
                continue
            level, name, conf = resolve_geo(geo_raw)
            if conf > 0:
                geo_level, geo_name, geo_conf = level, name, conf
            else:
                geo_name = geo_raw.strip()
                geo_level = "district"
                geo_conf = 0.5

        for col in df.columns:
            if col in {cat_col, geo_col}:
                continue
            m = YEAR_COL_RE.match(str(col).strip())
            # Also handle "2021 Reported" style with space
            if m is None:
                m2 = re.match(
                    r"^(20\d{2})\s+(reported|detected|cases?)$",
                    str(col).strip(),
                    re.I,
                )
                if not m2:
                    # columns like "2021 Reported" already covered; try split
                    parts = str(col).strip().split()
                    if len(parts) >= 2 and re.fullmatch(r"20\d{2}", parts[0]):
                        year = int(parts[0])
                        metric = parts[1].lower()
                        if metric.startswith("report"):
                            metric = "reported"
                        elif metric.startswith("detect"):
                            metric = "detected"
                        else:
                            metric = "value"
                    else:
                        continue
                else:
                    year = int(m2.group(1))
                    metric = m2.group(2).lower()
                    if metric.startswith("report"):
                        metric = "reported"
                    elif metric.startswith("detect"):
                        metric = "detected"
                    else:
                        metric = "value"
            else:
                year = int(m.group(1))
                metric_raw = m.group(2)
                metric = (metric_raw or "value").lower()
                if metric.startswith("report"):
                    metric = "reported"
                elif metric.startswith("detect"):
                    metric = "detected"

            value = _clean_number(series.get(col))
            if value is None:
                continue
            facts.append(
                _fact(
                    geo_level=geo_level,
                    geo_name=geo_name,
                    geo_code=None,
                    year=year,
                    month=None,
                    crime_category_source=str(category).strip(),
                    metric=metric,
                    value=value,
                    source_id=source_id,
                    source_url=source_url,
                    confidence=geo_conf,
                    extra={"raw_file": str(path.name)},
                )
            )
    return facts


def parse_opencity_district_total_csv(
    path: Path,
    *,
    source_id: str,
    source_url: str | None,
    year_hint: int | None = None,
) -> list[dict[str, Any]]:
    """Parse district/city total IPC/SLL style CSVs; keep Bengaluru-related rows."""
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read %s: %s", path, exc)
        return []

    if df.empty:
        return []

    # Normalize columns
    df.columns = [str(c).strip() for c in df.columns]
    geo_col = None
    for candidate in df.columns:
        cl = candidate.lower()
        if any(k in cl for k in ("district", "unit", "city", "commissionerate")):
            geo_col = candidate
            break
    if geo_col is None:
        geo_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    year = year_hint
    if year is None:
        m = re.search(r"(20\d{2})", path.name)
        year = int(m.group(1)) if m else None

    facts: list[dict[str, Any]] = []
    for _, series in df.iterrows():
        geo_raw = series.get(geo_col)
        if pd.isna(geo_raw):
            continue
        if not is_bengaluru_related(str(geo_raw)):
            continue
        level, name, conf = resolve_geo(str(geo_raw))
        for col in df.columns:
            if col == geo_col:
                continue
            cl = col.lower()
            if cl.startswith("sl") or cl in {"sl no", "sl. no", "s.no", "index"}:
                continue
            value = _clean_number(series.get(col))
            if value is None:
                continue
            # Split "... - I/V/R" harassment tables into category + metric
            col_flat = re.sub(r"\s+", " ", str(col).replace("\n", " ")).strip()
            m = re.search(r"^(.*?)\s*[-–]\s*(I|V|R|Incidents?|Victims?|Crime Rate)\s*(?:\([^)]*\))?$", col_flat, re.I)
            if m:
                category = m.group(1).strip()
                metric_token = m.group(2).lower()
                if metric_token.startswith("i"):
                    metric = "incidents"
                elif metric_token.startswith("v"):
                    metric = "victims"
                else:
                    metric = "rate_per_lakh"
            else:
                category = col_flat
                metric = "reported"
                if "ipc" in cl or "sll" in cl or "bns" in cl:
                    category = col_flat
            facts.append(
                _fact(
                    geo_level=level or "district",
                    geo_name=name or str(geo_raw).strip(),
                    geo_code=None,
                    year=year,
                    month=None,
                    crime_category_source=category,
                    metric=metric,
                    value=value,
                    source_id=source_id,
                    source_url=source_url,
                    confidence=conf or 0.6,
                    extra={"raw_file": path.name},
                )
            )
    return facts


def parse_idp_district_caw(
    path: Path,
    *,
    source_id: str,
    source_url: str | None,
) -> list[dict[str, Any]]:
    """Parse India Data Portal district CAW CSV; filter Karnataka Bengaluru rows."""
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read IDP CSV %s: %s", path, exc)
        return []

    if df.empty:
        return []

    df.columns = [str(c).strip() for c in df.columns]
    # Flexible column names
    colmap = {c.lower(): c for c in df.columns}

    def pick(*names: str) -> str | None:
        for n in names:
            if n in colmap:
                return colmap[n]
        for key, orig in colmap.items():
            for n in names:
                if n in key:
                    return orig
        return None

    year_col = pick("year")
    state_col = pick("state name", "state_name", "state")
    district_col = pick("district name", "district_name", "district")
    circles_col = pick("registration circles", "registration_circles")
    state_code_col = pick("state code", "state_code")
    district_code_col = pick("district code", "district_code")

    if district_col is None or year_col is None:
        logger.warning("IDP CSV missing year/district columns: %s", list(df.columns)[:10])
        return []

    # Filter Karnataka + Bengaluru-related (district or registration circle)
    work = df.copy()
    if state_col:
        mask_state = work[state_col].astype(str).str.contains("Karnataka", case=False, na=False)
        work = work[mask_state]

    def _row_is_bengaluru(row: pd.Series) -> bool:
        if is_bengaluru_related(str(row.get(district_col, ""))):
            return True
        if circles_col and is_bengaluru_related(str(row.get(circles_col, ""))):
            return True
        return False

    work = work[work.apply(_row_is_bengaluru, axis=1)]
    if work.empty:
        work = df[df.apply(_row_is_bengaluru, axis=1)]

    skip_cols = {
        year_col,
        state_col,
        district_col,
        circles_col,
        state_code_col,
        district_code_col,
        pick("index"),
        pick("id"),
    }
    skip_cols = {c for c in skip_cols if c}
    for c in list(work.columns):
        if str(c).strip().lower() in {"id", "index", "unnamed: 0"}:
            skip_cols.add(c)

    facts: list[dict[str, Any]] = []
    for _, series in work.iterrows():
        # Prefer registration circle (Bengaluru City / District / Railways)
        circle_raw = str(series.get(circles_col, "")).strip() if circles_col else ""
        district_raw = str(series.get(district_col, "")).strip()
        geo_raw = circle_raw if circle_raw and circle_raw.lower() not in {"", "nan", "none"} else district_raw
        level, name, conf = resolve_geo(geo_raw)
        # Keep railways distinct
        if "rail" in geo_raw.lower():
            level, name, conf = "city", "Bengaluru Railways", 0.85
        try:
            year = int(float(series[year_col]))
        except (TypeError, ValueError):
            continue
        geo_code = None
        if district_code_col and not pd.isna(series.get(district_code_col)):
            geo_code = str(series.get(district_code_col))
        for col in work.columns:
            if col in skip_cols:
                continue
            value = _clean_number(series.get(col))
            if value is None:
                continue
            facts.append(
                _fact(
                    geo_level=level or "district",
                    geo_name=name or geo_raw,
                    geo_code=geo_code,
                    year=year,
                    month=None,
                    crime_category_source=str(col).strip(),
                    metric="reported",
                    value=value,
                    source_id=source_id,
                    source_url=source_url,
                    confidence=conf or 0.8,
                    extra={
                        "raw_file": path.name,
                        "source_district": district_raw,
                        "registration_circle": circle_raw or None,
                    },
                )
            )
    return facts


def iter_csv_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob("*.csv"))


def year_from_source_id(source_id: str) -> int | None:
    m = re.search(r"(20\d{2})", source_id)
    return int(m.group(1)) if m else None