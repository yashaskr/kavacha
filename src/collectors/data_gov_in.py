"""data.gov.in catalog helpers (best-effort public resource discovery)."""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from src.catalog import sources_by_family
from src.collectors.base import CollectResult
from src.http_util import download_to_dir, raw_run_dir, request_get, write_lineage, utc_now_iso
from src.paths import RAW

logger = logging.getLogger(__name__)

# Known historical resource pages (public) — best-effort seeds when Catalog API needs a key
SEED_RESOURCES = [
    "https://data.gov.in/resource/district-wise-crimes-committed-against-women-during-2013",
    "https://www.data.gov.in/catalog/district-wise-crimes-committed-against-women",
]


def _extract_download_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        lower = href.lower()
        if any(lower.endswith(ext) for ext in (".csv", ".zip", ".xls", ".xlsx")):
            if href.startswith("http"):
                links.append(href)
            elif href.startswith("/"):
                links.append("https://www.data.gov.in" + href)
    # Also catch API-ish patterns in page text
    for match in re.findall(r"https?://[^\s\"']+\.(?:csv|zip|xls|xlsx)", html, flags=re.I):
        links.append(match)
    # dedupe
    seen: set[str] = set()
    out: list[str] = []
    for link in links:
        if link not in seen:
            seen.add(link)
            out.append(link)
    return out


def collect_datagov_source(source: dict[str, Any]) -> CollectResult:
    source_id = source["id"]
    run_dir = raw_run_dir(RAW, source_id)
    catalog_url = source.get("url")
    saved: list[str] = []
    pages = [catalog_url] if catalog_url else []
    pages.extend(SEED_RESOURCES)

    for page in pages:
        if not page:
            continue
        try:
            resp = request_get(page, timeout=60.0)
            (run_dir / "pages").mkdir(exist_ok=True)
            safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", page)[-80:]
            (run_dir / "pages" / f"{safe}.html").write_text(resp.text, encoding="utf-8")
            links = _extract_download_links(resp.text, page)
            write_lineage(
                run_dir,
                {
                    "source_id": source_id,
                    "url": page,
                    "retrieved_at": utc_now_iso(),
                    "ok": True,
                    "discovered_links": links,
                },
            )
            for link in links[:20]:
                path = download_to_dir(
                    link,
                    run_dir,
                    source_id=source_id,
                    license_note=source.get("licensing"),
                )
                if path:
                    saved.append(str(path))
        except Exception as exc:  # noqa: BLE001
            logger.warning("data.gov.in page failed %s: %s", page, exc)
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

    # Soft success: metadata capture counts even if downloads blocked (login walls)
    note_path = run_dir / "README_collector.txt"
    note_path.write_text(
        "data.gov.in often requires an API key for Catalog API and may gate CSV downloads.\n"
        "This collector saves page HTML + any public file links discovered.\n"
        "If empty, register at data.gov.in and set DATA_GOV_IN_API_KEY for a future enhancement.\n",
        encoding="utf-8",
    )
    ok = True  # catalog discovery is best-effort; do not fail the whole run
    return CollectResult(
        source_id=source_id,
        ok=ok,
        files=saved,
        message=f"Discovered/downloaded {len(saved)} files; see lineage and pages/",
    )


def collect_all() -> list[CollectResult]:
    results: list[CollectResult] = []
    for source in sources_by_family("data_gov_in"):
        if source.get("tier") == "C":
            continue
        logger.info("Collecting data.gov.in source %s", source["id"])
        results.append(collect_datagov_source(source))
    return results