"""Download NCRB CAW chapters/tables/XLSX for 2012-2016 backfill."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin, unquote, urlparse

from bs4 import BeautifulSoup

from src.collectors.base import CollectResult
from src.http_util import download_to_dir, raw_run_dir, request_get, write_lineage, utc_now_iso
from src.paths import RAW

logger = logging.getLogger(__name__)

YEARS = list(range(2012, 2017))

PAGE_TEMPLATES = [
    "https://www.ncrb.gov.in/crime-in-india-table-chapter.html?year={year}",
    "https://www.ncrb.gov.in/crime-in-india-additional-table?year={year}",
    "https://www.ncrb.gov.in/crime-in-india-table-content.html?year={year}",
]

# Explicit high-value seeds (stable NCRB upload paths discovered 2026-10)
SEED_URLS: dict[int, list[tuple[str, str]]] = {
    2012: [
        ("caw_chapter_2012.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/5-crime-against-women_2012.pdf"),
        ("table_5_1_2012.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table-5.1.pdf"),
        ("table_5_2_2012.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table5.2.pdf"),
    ],
    2013: [
        ("caw_chapter_2013.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/5-crime-against-women_2013.pdf"),
        ("table_5_1_2013.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table-5.1_2013.pdf"),
        ("table_5_2_2013.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table-5.2_2013.pdf"),
    ],
    2014: [
        ("caw_chapter_2014.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/chapter-5_2014.pdf"),
        ("district_caw_2014.xlsx", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/5District-wise-Crimes-committed-against-Women_2014.xlsx"),
        ("ncr_caw_2014.xlsx", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/NCR-Crimes-committed-against-Women_2014.xlsx"),
        ("table_5_1_2014.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table-5.1_2014.pdf"),
        ("table_5_2_2014.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table-5.2_2014.pdf"),
    ],
    2015: [
        ("caw_chapter_2015.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/chapter-5-15.11.16_2015.pdf"),
        ("district_caw_2015.xlsx", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/5-District-wise-Crimes-committed-against-Women_2015.xlsx"),
        ("ncr_caw_2015.xlsx", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/NCR-Crimes-committed-against-Women_2015.xlsx"),
        ("table_5_1_2015.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table-5.1_2015.pdf"),
        ("table_5_2_2015.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table-5.2_2015.pdf"),
    ],
    2016: [
        ("district_caw_2016.xlsx", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/District-wise-Crimes-committed-against-Women_2016.xlsx"),
        ("table_3b1_2016.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table-3B.1.pdf"),
        ("table_3b2i_2016.pdf", "https://www.ncrb.gov.in/uploads/2022/July/11/custom/crime-in-india/Table-3B.2.pdf"),
    ],
}

KEEP_RE = re.compile(
    r"(crime\s*against\s*women|chapter[-_ ]?5|table[-_ ]?5\.|table[-_ ]?3b|"
    r"district[-_ ]?wise.*women|ncr[-_ ].*women|5district|women_20\d{2})",
    re.I,
)
DROP_RE = re.compile(
    r"(internship|newsletter|aibe|hackathon|icc-women|feedback|foreword|"
    r"disclaimer|limitations|publication team|children|juvenile)",
    re.I,
)


def _ascii_name(label: str, url: str, year: int, idx: int) -> str:
    url_name = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    ascii_name = "".join(c if ord(c) < 128 and (c.isalnum() or c in "._-") else "_" for c in url_name)
    ascii_name = re.sub(r"_+", "_", ascii_name).strip("_")
    if not ascii_name or len(ascii_name) < 5:
        ext = ".pdf"
        for candidate in (".xlsx", ".xls", ".pdf"):
            if url.lower().endswith(candidate):
                ext = candidate
                break
        ascii_name = f"ncrb_caw_{year}_{idx:02d}{ext}"
    return ascii_name[:180]


def _discover_year(year: int) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for template in PAGE_TEMPLATES:
        page = template.format(year=year)
        try:
            resp = request_get(page, timeout=90)
        except Exception as exc:  # noqa: BLE001
            logger.warning("NCRB backfill page failed %s: %s", page, exc)
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            label = " ".join((a.get_text() or "").split())
            if label.startswith("["):
                continue
            full = urljoin(str(resp.url), href)
            blob = f"{label} {full}"
            if DROP_RE.search(blob):
                continue
            if not KEEP_RE.search(blob):
                continue
            if not any(full.lower().endswith(ext) for ext in (".pdf", ".xlsx", ".xls")):
                continue
            found.append((label, full))
    # seeds first
    seeded = list(SEED_URLS.get(year, []))
    seen = {u for _, u in seeded}
    out = [(name, url) for name, url in seeded]
    for label, url in found:
        if url in seen:
            continue
        seen.add(url)
        out.append((label, url))
    return out


def collect_backfill(years: list[int] | None = None) -> CollectResult:
    source_id = "ncrb_caw_backfill_2012_2016"
    years = years or YEARS
    run_dir = raw_run_dir(RAW, source_id)
    saved: list[str] = []
    discovered_lines: list[str] = []

    for year in years:
        year_dir = run_dir / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        items = _discover_year(year)
        write_lineage(
            run_dir,
            {
                "source_id": source_id,
                "year": year,
                "retrieved_at": utc_now_iso(),
                "discovered": [{"label": l, "url": u} for l, u in items],
            },
        )
        for idx, (label, url) in enumerate(items, start=1):
            discovered_lines.append(f"{year}\t{label}\t{url}")
            filename = label if label.endswith((".pdf", ".xlsx", ".xls")) else _ascii_name(label, url, year, idx)
            if not any(filename.lower().endswith(ext) for ext in (".pdf", ".xlsx", ".xls")):
                filename = _ascii_name(label, url, year, idx)
            path = download_to_dir(
                url,
                year_dir,
                source_id=source_id,
                filename=filename,
                license_note="NCRB Crime in India / GoI publication",
            )
            if path:
                saved.append(str(path))

    (run_dir / "discovered_backfill.txt").write_text("\n".join(discovered_lines), encoding="utf-8")
    return CollectResult(
        source_id=source_id,
        ok=len(saved) > 0,
        files=saved,
        message=f"Downloaded {len(saved)} CAW backfill artifacts for {years}",
        error=None if saved else "No backfill files downloaded",
    )


def collect_all() -> list[CollectResult]:
    logger.info("Collecting NCRB CAW backfill 2012-2016")
    return [collect_backfill()]
