"""Discover and download NCRB Crime in India PDF reports."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.catalog import sources_by_family
from src.collectors.base import CollectResult
from src.http_util import download_to_dir, raw_run_dir, request_get, write_lineage, utc_now_iso
from src.paths import RAW

logger = logging.getLogger(__name__)

YEAR_PAGE = "https://www.ncrb.gov.in/crime-in-india-year-wise.html?year={year}&keyword="
EXTRA_PAGES = [
    "https://www.ncrb.gov.in/crime-in-india.html",
    "https://www.ncrb.gov.in/crime-in-india-all-previous-publications.html",
]

# Keep only Crime-in-India style artifacts
KEEP_RE = re.compile(
    r"(crime\s*in\s*india|cii[-\s_]?20\d{2}|volume\s*[-_]?\s*[i1-3]|snapshots?\s*(states|cities)|"
    r"women|against\s*women|chapter\s*5|ch-?5)",
    re.I,
)
DROP_RE = re.compile(
    r"(internship|newsletter|trainingcalendar|aibe|hackathon|icc-women|feedback|"
    r"corrigendum|glossary|foreword|disclaimer|methodology|caution|annexure|"
    r"officers|population|getlatlng)",
    re.I,
)


def _find_cii_pdf_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Return list of (label, url) for likely Crime in India PDFs."""
    soup = BeautifulSoup(html, "lxml")
    found: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if ".pdf" not in href.lower():
            continue
        label = " ".join((a.get_text() or "").split())
        full = urljoin(base_url, href)
        blob = f"{label} {full}"
        if DROP_RE.search(blob):
            continue
        if KEEP_RE.search(blob) or re.search(r"CII|Crime%20in%20India|Crime in India", full, re.I):
            found.append((label or full.rsplit("/", 1)[-1], full))
        # Year-wise chapter PDFs often have opaque names under /uploads/files/
        # Keep volume-like short numeric names only when page is year-wise CII.
        elif re.search(r"/uploads/files/\d", full) and re.search(
            r"volume|snapshot|झलक|विषय|महिला|women", label, re.I
        ):
            found.append((label or full.rsplit("/", 1)[-1], full))
    # dedupe by URL
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for label, url in found:
        if url not in seen:
            seen.add(url)
            out.append((label, url))
    return out


def collect_ncrb_source(source: dict[str, Any]) -> CollectResult:
    source_id = source["id"]
    run_dir = raw_run_dir(RAW, source_id)
    current_year = datetime.now(timezone.utc).year
    years = list(range(2012, current_year + 1))

    pages = [YEAR_PAGE.format(year=y) for y in years] + EXTRA_PAGES
    discovered: list[tuple[str, str, str]] = []  # label, url, page

    for page in pages:
        try:
            resp = request_get(page, timeout=90.0)
            (run_dir / "pages").mkdir(exist_ok=True)
            fname = re.sub(r"[^a-zA-Z0-9_-]+", "_", page)[-100:] + ".html"
            (run_dir / "pages" / fname).write_text(resp.text, encoding="utf-8")
            pdfs = _find_cii_pdf_links(resp.text, str(resp.url))
            for label, url in pdfs:
                discovered.append((label, url, page))
            write_lineage(
                run_dir,
                {
                    "source_id": source_id,
                    "url": page,
                    "retrieved_at": utc_now_iso(),
                    "ok": True,
                    "pdf_links": [u for _, u in pdfs],
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("NCRB page failed %s: %s", page, exc)
            write_lineage(
                run_dir,
                {
                    "source_id": source_id,
                    "url": page,
                    "retrieved_at": utc_now_iso(),
                    "ok": False,
                    "error": str(exc),
                },
            )

    # Prefer clear CII volume / women / snapshot PDFs; cap downloads
    ranked = sorted(
        discovered,
        key=lambda t: (
            0 if re.search(r"volume|Crime in India|CII-20", t[0] + t[1], re.I) else 1,
            0 if re.search(r"women|महिला", t[0] + t[1], re.I) else 1,
            t[1],
        ),
    )
    unique_urls: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, url, _page in ranked:
        if url in seen:
            continue
        seen.add(url)
        unique_urls.append((label, url))

    saved: list[str] = []
    # Download up to 25 relevant PDFs (volumes are large)
    for idx, (label, url) in enumerate(unique_urls[:25], start=1):
        # ASCII-safe names (Hindi labels break Windows consoles / some filesystems)
        from urllib.parse import unquote, urlparse
        import hashlib

        url_name = unquote(urlparse(url).path.rsplit("/", 1)[-1])
        ascii_from_url = "".join(c if ord(c) < 128 and (c.isalnum() or c in "._-") else "_" for c in url_name)
        ascii_from_url = re.sub(r"_+", "_", ascii_from_url).strip("_")
        if not ascii_from_url.lower().endswith(".pdf"):
            digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
            ascii_from_url = f"cii_{idx:02d}_{digest}.pdf"
        path = download_to_dir(
            url,
            run_dir / "cii_pdfs",
            source_id=source_id,
            filename=ascii_from_url[:180],
            license_note=source.get("licensing"),
        )
        if path:
            saved.append(str(path))

    (run_dir / "discovered_cii_pdfs.txt").write_text(
        "\n".join(f"{label}\t{url}" for label, url in unique_urls),
        encoding="utf-8",
    )
    return CollectResult(
        source_id=source_id,
        ok=True,
        files=saved,
        message=f"Discovered {len(unique_urls)} CII PDFs; downloaded {len(saved)}",
    )


def collect_all() -> list[CollectResult]:
    results: list[CollectResult] = []
    for source in sources_by_family("ncrb_pdf"):
        logger.info("Collecting NCRB PDF source %s", source["id"])
        results.append(collect_ncrb_source(source))
    return results
