"""OpenCity CKAN collectors for crime stats and GIS packages."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

from src.catalog import sources_by_family
from src.collectors.base import CollectResult
from src.http_util import download_to_dir, fetch_json, raw_run_dir
from src.paths import RAW, REFERENCE

logger = logging.getLogger(__name__)

INTERESTING_FORMATS = {
    "csv",
    "pdf",
    "kml",
    "kmz",
    "geojson",
    "json",
    "zip",
    "xlsx",
    "xls",
    "shp",
    "gpkg",
}


def _package_show(ckan_base: str, package_name: str) -> dict[str, Any]:
    api = urljoin(ckan_base.rstrip("/") + "/", "api/3/action/package_show")
    data = fetch_json(f"{api}?id={package_name}")
    if not data.get("success"):
        raise RuntimeError(f"CKAN package_show failed for {package_name}: {data}")
    return data["result"]


def _resource_url(resource: dict[str, Any]) -> str | None:
    return resource.get("url") or resource.get("download_url")


def collect_opencity_source(source: dict[str, Any]) -> CollectResult:
    source_id = source["id"]
    package = source.get("ckan_package")
    ckan_base = source.get("ckan_base", "https://data.opencity.in")
    if not package:
        return CollectResult(source_id, False, error="missing ckan_package")

    target_root = REFERENCE if source.get("target_dir") == "reference" else RAW
    run_dir = raw_run_dir(target_root, source_id)

    try:
        pkg = _package_show(ckan_base, package)
    except Exception as exc:  # noqa: BLE001
        logger.exception("OpenCity package fetch failed: %s", source_id)
        return CollectResult(source_id, False, error=str(exc))

    # Persist package metadata for lineage / debugging
    meta_path = run_dir / "package_show.json"
    import json

    meta_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")

    saved: list[str] = []
    for resource in pkg.get("resources", []):
        fmt = (resource.get("format") or "").strip().lower()
        url = _resource_url(resource)
        if not url:
            continue
        # Prefer known data formats; still allow blank format if URL looks useful
        ext = url.rsplit(".", 1)[-1].lower() if "." in url else ""
        if fmt and fmt not in INTERESTING_FORMATS and ext not in INTERESTING_FORMATS:
            continue
        name = resource.get("name") or resource.get("id")
        # sanitize filename
        safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in str(name)).strip()
        if safe and ext and not safe.lower().endswith(f".{ext}"):
            filename = f"{safe}.{ext}" if ext in INTERESTING_FORMATS else safe
        else:
            filename = safe or None
        path = download_to_dir(
            url,
            run_dir,
            source_id=source_id,
            filename=filename,
            license_note=source.get("licensing"),
        )
        if path:
            saved.append(str(path))

    ok = len(saved) > 0
    return CollectResult(
        source_id=source_id,
        ok=ok,
        files=saved,
        message=f"Downloaded {len(saved)} resources from {package}",
        error=None if ok else "No resources downloaded",
    )


def collect_all(families: list[str] | None = None) -> list[CollectResult]:
    families = families or ["opencity", "gis_opencity"]
    results: list[CollectResult] = []
    for family in families:
        for source in sources_by_family(family):
            if source.get("tier") == "C":
                continue
            logger.info("Collecting OpenCity source %s", source["id"])
            results.append(collect_opencity_source(source))
    return results