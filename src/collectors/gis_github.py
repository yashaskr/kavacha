"""GitHub release downloads for india-geodata police boundaries."""

from __future__ import annotations

import logging

from src.catalog import sources_by_family
from src.collectors.base import CollectResult
from src.http_util import download_to_dir, raw_run_dir
from src.paths import REFERENCE

logger = logging.getLogger(__name__)


def collect_github_source(source: dict) -> CollectResult:
    source_id = source["id"]
    urls = source.get("download_urls") or []
    if not urls and source.get("download_url"):
        urls = [source["download_url"]]
    if not urls:
        return CollectResult(source_id, False, error="No download_urls")

    run_dir = raw_run_dir(REFERENCE, source_id)
    saved: list[str] = []
    for url in urls:
        # Prefer parquet over large pmtiles for MVP; still try both
        path = download_to_dir(
            url,
            run_dir,
            source_id=source_id,
            license_note=source.get("licensing"),
        )
        if path:
            saved.append(str(path))

    ok = len(saved) > 0
    return CollectResult(
        source_id=source_id,
        ok=ok,
        files=saved,
        message=f"Downloaded {len(saved)} GIS artifacts",
        error=None if ok else "All GIS downloads failed",
    )


def collect_all() -> list[CollectResult]:
    results: list[CollectResult] = []
    for source in sources_by_family("gis_github"):
        logger.info("Collecting GitHub GIS source %s", source["id"])
        results.append(collect_github_source(source))
    return results