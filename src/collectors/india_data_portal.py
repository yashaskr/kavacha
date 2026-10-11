"""India Data Portal direct CSV downloads."""

from __future__ import annotations

import logging

from src.catalog import sources_by_family
from src.collectors.base import CollectResult
from src.http_util import download_to_dir, raw_run_dir
from src.paths import RAW

logger = logging.getLogger(__name__)


def collect_idp_source(source: dict) -> CollectResult:
    source_id = source["id"]
    url = source.get("download_url") or source.get("url")
    if not url or not str(url).endswith((".csv", ".CSV")) and "download" not in str(url):
        # Still try download_url if present
        url = source.get("download_url")
    if not url:
        return CollectResult(source_id, False, error="No download_url configured")

    run_dir = raw_run_dir(RAW, source_id)
    path = download_to_dir(
        url,
        run_dir,
        source_id=source_id,
        filename="districtwise-crime-against-women-2017-onwards.csv",
        license_note=source.get("licensing"),
    )
    if path is None:
        return CollectResult(source_id, False, error="Download failed")
    return CollectResult(source_id, True, files=[str(path)], message="IDP CSV downloaded")


def collect_all() -> list[CollectResult]:
    results: list[CollectResult] = []
    for source in sources_by_family("india_data_portal"):
        if source.get("tier") == "C":
            continue
        logger.info("Collecting IDP source %s", source["id"])
        results.append(collect_idp_source(source))
    return results