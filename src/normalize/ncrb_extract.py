"""Extract Bengaluru CAW aggregates from NCRB PDFs and Excel files (2012-2016)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterable

import pdfplumber
import pandas as pd

from src.http_util import utc_now_iso
from src.normalize.geo import resolve_geo
from src.normalize.taxonomy import normalize_category

logger = logging.getLogger(__name__)

CITY_RE = re.compile(r"\b(Bengaluru|Bangalore)\b", re.I)
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _fact(
    *,
    year: int,
    geo_name: str,
    geo_level: str,
    category: str,
    metric: str,
    value: float,
    source_id: str,
    source_url: str | None,
    raw_file: str,
    confidence: float,
) -> dict[str, Any]:
    cat, cat_conf = normalize_category(category)
    return {
        "geo_level": geo_level,
        "geo_name": geo_name,
        "geo_code": None,
        "year": year,
        "month": None,
        "crime_category_source": category,
        "crime_category_normalized": cat,
        "metric": metric,
        "value": value,
        "source_id": source_id,
        "source_url": source_url,
        "retrieved_at": utc_now_iso(),
        "confidence": min(confidence, cat_conf),
        "category_confidence": cat_conf,
        "raw_file": raw_file,
        "source_district": None,
        "registration_circle": None,
    }


def _parse_number_tokens(text: str) -> list[float]:
    return [float(x) for x in NUM_RE.findall(text)]


def _city_geo(label: str) -> tuple[str, str, float]:
    level, name, conf = resolve_geo(label)
    if conf > 0 and name:
        return level or "city", name, conf
    return "city", "Bengaluru City", 0.8


def extract_from_pdf_text(
    path: Path,
    *,
    year_hint: int | None,
    source_id: str,
    source_url: str | None,
) -> list[dict[str, Any]]:
    """Parse Bengaluru/Bangalore lines from CAW-related PDF pages."""
    facts: list[dict[str, Any]] = []
    try:
        pdf = pdfplumber.open(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cannot open PDF %s: %s", path, exc)
        return []

    with pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not text:
                continue
            low = text.lower()
            # Keep women / metro / city incidence tables (incl. "Table-5.1 (Concluded)" pages)
            relevant = (
                "crime against women" in low
                or "crimes against women" in low
                or "crime committed against women" in low
                or "table 3b" in low
                or "table-3b" in low
                or "table 5." in low
                or "table-5" in low
                or ("incidence" in low and "women" in low)
                or ("cities:" in low and "incidence" in low)
            )
            if not relevant:
                continue
            if not CITY_RE.search(text):
                continue

            year = year_hint
            ym = re.search(r"(20\d{2})", path.name)
            if year is None and ym:
                year = int(ym.group(1))

            # Multi-year metro total table (e.g. 3B.1: City 2014 2015 2016 ...)
            years_header = None
            title_span = re.search(
                r"Metropolitan Cities\s*[-–]\s*(20\d{2})\s*[-–]\s*(20\d{2})",
                text,
                re.I,
            )
            if title_span:
                y0, y1 = int(title_span.group(1)), int(title_span.group(2))
                if 2010 <= y0 <= y1 <= 2030 and (y1 - y0) <= 5:
                    years_header = list(range(y0, y1 + 1))
            if years_header is None:
                header_years = re.findall(
                    r"\b(20\d{2})\b",
                    "\n".join(text.splitlines()[:20]),
                )
                seen = []
                for y in header_years:
                    yi = int(y)
                    # Only accept recent contiguous report years near hint
                    if year and abs(yi - int(year)) > 3:
                        continue
                    if yi not in seen and 2010 <= yi <= 2030:
                        seen.append(yi)
                if 2 <= len(seen) <= 4:
                    years_header = seen

            for raw_line in text.splitlines():
                line = " ".join(raw_line.split())
                if not CITY_RE.search(line):
                    continue
                # Skip pure narrative lines
                nums = _parse_number_tokens(CITY_RE.split(line, maxsplit=1)[-1])
                if not nums:
                    continue

                geo_level, geo_name, geo_conf = _city_geo(line)

                # Case A: multi-year totals (first 3 ints are case counts)
                if years_header and len(nums) >= len(years_header):
                    # Heuristic: first N integers (no decimals) map to year totals
                    ints = [n for n in nums if float(n).is_integer()]
                    if len(ints) >= len(years_header):
                        for y, val in zip(years_header, ints[: len(years_header)]):
                            if val <= 0:
                                continue
                            facts.append(
                                _fact(
                                    year=int(y),
                                    geo_name=geo_name,
                                    geo_level=geo_level,
                                    category="Total Crimes Against Women",
                                    metric="reported",
                                    value=float(val),
                                    source_id=source_id,
                                    source_url=source_url,
                                    raw_file=path.name,
                                    confidence=max(0.75, geo_conf),
                                )
                            )
                        continue

                # Case B: single-year incidence table — first large int is total cases
                if year is None:
                    continue
                # Avoid non-CAW metro crime tables in the full publication
                caw_page = (
                    "crime against women" in low
                    or "crimes against women" in low
                    or "crime committed against women" in low
                    or "table-5.1" in low
                    or "table 5.1" in low
                    or ("cities:" in low and "incidence" in low)
                )
                if not caw_page:
                    continue
                if "table 1b" in low or "ipc crimes in metropolitan" in low:
                    continue
                ints = [int(n) for n in nums if float(n).is_integer()]
                if not ints:
                    continue
                # Prefer values that look like case counts (not ranks/rates/year tokens)
                candidates = [n for n in ints if 1 <= n <= 50000 and n != int(year)]
                if not candidates:
                    continue
                # For Table 5.1 style: often [incidence, rate-ish, ...] — take first
                total = candidates[0]
                conf = 0.9 if re.search(r"table[-_ ]?5\.1|table 5\.1", low) else 0.7
                facts.append(
                    _fact(
                        year=int(year),
                        geo_name=geo_name,
                        geo_level=geo_level,
                        category="Total Crimes Against Women",
                        metric="reported",
                        value=float(total),
                        source_id=source_id,
                        source_url=source_url,
                        raw_file=path.name,
                        confidence=conf,
                    )
                )

                # If I/V/R triples present on category continuation pages, capture
                # first-of-triple values with generic labels from nearby headers.
                if "I V R" in text or re.search(r"\bI\s+V\s+R\b", text):
                    triples = []
                    i = 0
                    while i + 2 < len(nums):
                        a, b, c = nums[i], nums[i + 1], nums[i + 2]
                        # I/V often ints, R often decimal
                        triples.append((a, b, c))
                        i += 3
                    # Map via simple keyword scan of page header block
                    header_block = " ".join(text.splitlines()[:35])
                    cats = _infer_categories_from_header(header_block, len(triples))
                    for cat, triple in zip(cats, triples):
                        incidents = triple[0]
                        if incidents < 0:
                            continue
                        facts.append(
                            _fact(
                                year=int(year),
                                geo_name=geo_name,
                                geo_level=geo_level,
                                category=cat,
                                metric="incidents",
                                value=float(incidents),
                                source_id=source_id,
                                source_url=source_url,
                                raw_file=path.name,
                                confidence=0.65,
                            )
                        )

    return facts


def _infer_categories_from_header(header: str, n: int) -> list[str]:
    """Best-effort category labels from a CAW table header block."""
    patterns = [
        (r"Dowry Deaths", "Dowry Deaths"),
        (r"Abetment of Suicide", "Abetment of Suicide of Women"),
        (r"Causing miscarriage", "Causing Miscarriage"),
        (r"Acid Attack", "Acid Attack"),
        (r"Cruelty by Husband", "Cruelty by Husband or his Relatives"),
        (r"Kidnapping & Abduction of Women \(Total\)|Kidnapping & Abduction of\s*Women \(Total\)", "Kidnapping & Abduction of Women"),
        (r"Kidnapping & Abduction \(Sec\.363", "Kidnapping & Abduction (Sec.363 IPC)"),
        (r"Kidnapping for\s*Ransom", "Kidnapping for Ransom"),
        (r"Compel.*Marriage|women Marriage", "Kidnapping to Compel Marriage"),
        (r"Human Trafficking", "Human Trafficking"),
        (r"Rape \(Total\)|Rape\*", "Rape (Total)"),
        (r"Gang Rape", "Gang Rape"),
        (r"Custodial Rape", "Custodial Rape"),
        (r"Attempt to Commit Rape", "Attempt to Commit Rape"),
        (r"Unnatural Offences", "Unnatural Offences"),
        (r"Assault On Women \(Total\)|Assault On Women With Intent To Outrage Her Modesty", "Assault on Women (Total)"),
        (r"Sexual Harrassment|Sexual Harassment", "Sexual Harassment"),
        (r"Disrobe", "Assault to Disrobe"),
        (r"Voyeurism", "Voyeurism"),
        (r"Stalking", "Stalking"),
        (r"Insult to Modesty", "Insult to the Modesty of Women"),
        (r"Total IPC Crimes\s*against Women", "Total IPC Crimes against Women"),
        (r"Dowry Prohibition", "Dowry Prohibition Act"),
        (r"Immoral Traffic.*Total|Immoral Traffic \(Prevention\) Act 1956 \(Women Cases only\)-Total", "Immoral Traffic Act (Women)"),
        (r"Publishing or\s*Transmitting|Sexually Explicit", "Cyber Sexually Explicit Material"),
        (r"Total SLL Crimes\s*against Women", "Total SLL Crimes against Women"),
        (r"Total Crime against\s*Women \(IPC\+SLL\)", "Total Crimes Against Women"),
    ]
    found: list[str] = []
    for pat, label in patterns:
        if re.search(pat, header, re.I):
            found.append(label)
    if len(found) >= n:
        return found[:n]
    # Pad with generic labels
    while len(found) < n:
        found.append(f"CAW category {len(found) + 1}")
    return found


def extract_from_excel(
    path: Path,
    *,
    year_hint: int | None,
    source_id: str,
    source_url: str | None,
) -> list[dict[str, Any]]:
    """Parse district/city CAW Excel for Bengaluru/Bangalore rows."""
    try:
        sheets = pd.read_excel(path, sheet_name=None, header=None, engine=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cannot read Excel %s: %s", path, exc)
        return []

    year = year_hint
    if year is None:
        m = re.search(r"(20\d{2})", path.name)
        year = int(m.group(1)) if m else None
    if year is None:
        return []

    facts: list[dict[str, Any]] = []
    for sheet_name, df in sheets.items():
        if df is None or df.empty:
            continue
        # Find header row containing crime-like names
        header_idx = None
        for i in range(min(15, len(df))):
            row_vals = [str(v) for v in df.iloc[i].tolist() if pd.notna(v)]
            joined = " ".join(row_vals).lower()
            if any(k in joined for k in ("rape", "dowry", "cruelty", "district", "city", "state")):
                header_idx = i
                break
        if header_idx is None:
            continue

        header = []
        seen_headers: dict[str, int] = {}
        for j, v in enumerate(df.iloc[header_idx].tolist()):
            base = str(v).strip() if pd.notna(v) else f"col_{j}"
            if base in seen_headers:
                seen_headers[base] += 1
                header.append(f"{base}_{seen_headers[base]}")
            else:
                seen_headers[base] = 0
                header.append(base)
        body = df.iloc[header_idx + 1 :].copy()
        body.columns = header

        # Identify geo column index (avoid duplicate-label Series ambiguity)
        geo_idx = 0
        for j, c in enumerate(body.columns):
            cl = str(c).lower()
            if any(k in cl for k in ("district", "city", "state", "name", "unit")):
                geo_idx = j
                break

        for row in body.itertuples(index=False, name=None):
            if not row:
                continue
            geo_raw = row[geo_idx] if geo_idx < len(row) else None
            if geo_raw is None or (isinstance(geo_raw, float) and pd.isna(geo_raw)):
                # Fall back: scan whole row text
                row_join = " ".join(str(v) for v in row if v is not None and not (isinstance(v, float) and pd.isna(v)))
                m = CITY_RE.search(row_join)
                if not m:
                    continue
                geo_text = m.group(0)
            else:
                geo_text = str(geo_raw)
                if not CITY_RE.search(geo_text):
                    row_join = " ".join(str(v) for v in row if v is not None and not (isinstance(v, float) and pd.isna(v)))
                    m = CITY_RE.search(row_join)
                    if not m:
                        continue
                    geo_text = m.group(0)

            level, name, conf = _city_geo(geo_text)
            for j, col in enumerate(body.columns):
                if j == geo_idx:
                    continue
                val = row[j]
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    continue
                try:
                    num = float(str(val).replace(",", ""))
                except ValueError:
                    continue
                col_l = str(col).lower()
                if col_l in {"s.no", "sl", "sl no", "sno", "rank"}:
                    continue
                metric = "rate_per_lakh" if "rate" in col_l else "reported"
                category = str(col).strip()
                if category.lower() in {"total", "grand total"}:
                    category = "Total Crimes Against Women"
                facts.append(
                    _fact(
                        year=int(year),
                        geo_name=name,
                        geo_level=level,
                        category=category,
                        metric=metric,
                        value=num,
                        source_id=source_id,
                        source_url=source_url,
                        raw_file=f"{path.name}::{sheet_name}",
                        confidence=max(0.8, conf),
                    )
                )
    return facts


def iter_backfill_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for ext in ("*.pdf", "*.xlsx", "*.xls"):
        files.extend(root.rglob(ext))
    return sorted(files)


def _is_priority_backfill_file(path: Path) -> bool:
    name = path.name.lower()
    if any(k in name for k in ("disposal", "arrested", "offender", "age-group", "age_group")):
        return False
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return any(
            k in name
            for k in (
                "district",
                "ncr_caw",
                "ncr-crimes",
                "women_201",
                "against-women",
                "against_women",
            )
        )
    # PDFs: chapter / table 5.1-5.2 / 3B.1-3B.2 incidence
    return any(
        k in name
        for k in (
            "caw_chapter",
            "crime-against-women",
            "crime_against_women",
            "chapter-5",
            "chapter_5",
            "table_5_1",
            "table-5.1",
            "table5.1",
            "table_5_2",
            "table-5.2",
            "table5.2",
            "table-3b.1",
            "table3b1",
            "table-3b.2",
            "table3b2",
            "3b.1",
            "3b.2",
        )
    )


def extract_backfill_dir(
    run_dir: Path,
    *,
    source_id: str = "ncrb_caw_backfill_2012_2016",
    source_url: str = "https://www.ncrb.gov.in/crime-in-india-table-content.html",
) -> list[dict[str, Any]]:
    """Extract facts from a backfill run directory (year subfolders + cii pdfs)."""
    facts: list[dict[str, Any]] = []

    # Year-partitioned backfill downloads
    for year_dir in sorted(p for p in run_dir.iterdir() if p.is_dir() and p.name.isdigit()):
        year = int(year_dir.name)
        for path in iter_backfill_files(year_dir):
            if not _is_priority_backfill_file(path):
                continue
            logger.info("Extracting %s", path.name)
            try:
                if path.suffix.lower() == ".pdf":
                    facts.extend(
                        extract_from_pdf_text(
                            path,
                            year_hint=year,
                            source_id=source_id,
                            source_url=source_url,
                        )
                    )
                else:
                    facts.extend(
                        extract_from_excel(
                            path,
                            year_hint=year,
                            source_id=source_id,
                            source_url=source_url,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Extract failed for %s: %s", path.name, exc)

    # Prefer the single full 2016 publication (skip duplicate Volume-* copies)
    cii_dir = run_dir / "cii_pdfs"
    if cii_dir.exists():
        preferred = sorted(
            p
            for p in cii_dir.glob("*.pdf")
            if "crime in india 2016" in p.name.lower() or "full publication" in p.name.lower()
        )
        for path in preferred[:1]:
            logger.info("Extracting full publication PDF %s", path.name)
            facts.extend(
                extract_from_pdf_text(
                    path,
                    year_hint=2016,
                    source_id=source_id,
                    source_url=source_url,
                )
            )

    # Deduplicate exact facts, then collapse competing totals for same year/geo
    seen = set()
    unique: list[dict[str, Any]] = []
    for f in facts:
        key = (
            f.get("year"),
            f.get("geo_name"),
            f.get("crime_category_source"),
            f.get("metric"),
            f.get("value"),
            f.get("raw_file"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)

    def _total_rank(f: dict[str, Any]) -> tuple:
        name = str(f.get("raw_file", "")).lower()
        # Prefer dedicated incidence tables over full-book noise
        pref = 0
        if "3b.1" in name or "3b1" in name or "table_5_1" in name or "table-5.1" in name:
            pref = 3
        elif "caw_chapter" in name or "district_caw" in name or "ncr_caw" in name:
            pref = 2
        elif "full publication" in name:
            pref = 0
        else:
            pref = 1
        return (pref, float(f.get("confidence") or 0))

    collapsed: dict[tuple, dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for f in unique:
        is_total = (
            str(f.get("crime_category_normalized")) == "Total Crimes Against Women"
            and str(f.get("metric")) in {"reported", "incidents", "value"}
        )
        if not is_total:
            passthrough.append(f)
            continue
        key = (f.get("year"), f.get("geo_name"), "total_caw")
        prev = collapsed.get(key)
        if prev is None or _total_rank(f) > _total_rank(prev):
            collapsed[key] = f
    return passthrough + list(collapsed.values())
