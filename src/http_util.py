"""HTTP download helpers with retries and lineage."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "BengaluruWomenSafetyDataCollector/0.1 (+civic research; respectful crawl)"
}


_VERIFY_FALLBACK_WARNED = False


def _env_insecure() -> bool:
    return os.environ.get("WS_DATA_INSECURE_SSL", "").strip() in {"1", "true", "TRUE", "yes"}


def _ssl_verify() -> bool | str:
    """Return httpx verify setting.

    Prefer certifi CA bundle. Set WS_DATA_INSECURE_SSL=1 to force-disable verify
    (needed on some Windows/corporate proxy setups).
    """
    if _env_insecure():
        return False
    try:
        import certifi

        return certifi.where()
    except Exception:  # noqa: BLE001
        return True


def http_client(timeout: float = 120.0, verify: bool | str | None = None) -> httpx.Client:
    return httpx.Client(
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
        timeout=timeout,
        verify=_ssl_verify() if verify is None else verify,
    )


def _is_ssl_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "certificate" in msg or "ssl" in msg or "tls" in msg


def request_get(url: str, timeout: float = 120.0) -> httpx.Response:
    """GET with optional one-time insecure fallback after SSL failures."""
    global _VERIFY_FALLBACK_WARNED
    try:
        with http_client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp
    except Exception as exc:
        if _env_insecure() or not _is_ssl_error(exc):
            raise
        if not _VERIFY_FALLBACK_WARNED:
            logger.warning(
                "TLS verification failed (%s); retrying with verify=False. "
                "Set WS_DATA_INSECURE_SSL=1 to silence this warning.",
                exc,
            )
            _VERIFY_FALLBACK_WARNED = True
        with http_client(timeout=timeout, verify=False) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def filename_from_url(url: str, default: str = "download.bin") -> str:
    path = unquote(urlparse(url).path)
    name = Path(path).name
    return name or default


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20), reraise=True)
def fetch_bytes(url: str, timeout: float = 120.0) -> tuple[bytes, int, dict[str, str]]:
    resp = request_get(url, timeout=timeout)
    headers = {k: v for k, v in resp.headers.items()}
    return resp.content, resp.status_code, headers


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20), reraise=True)
def fetch_json(url: str, timeout: float = 60.0) -> Any:
    return request_get(url, timeout=timeout).json()


def write_lineage(dest_dir: Path, record: dict[str, Any]) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "lineage.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def download_to_dir(
    url: str,
    dest_dir: Path,
    *,
    source_id: str,
    filename: str | None = None,
    license_note: str | None = None,
) -> Path | None:
    """Download URL into dest_dir without overwriting different content.

    If the same filename already exists with identical hash, skip rewrite.
    If hash differs, write alongside with hash suffix.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = filename or filename_from_url(url)
    try:
        content, status, headers = fetch_bytes(url)
    except Exception as exc:  # noqa: BLE001 - fail soft per source
        logger.error("Download failed for %s (%s): %s", source_id, url, exc)
        write_lineage(
            dest_dir,
            {
                "source_id": source_id,
                "url": url,
                "retrieved_at": utc_now_iso(),
                "ok": False,
                "error": str(exc),
            },
        )
        return None

    digest = sha256_bytes(content)
    target = dest_dir / name
    if target.exists():
        existing = sha256_bytes(target.read_bytes())
        if existing == digest:
            logger.info("Skip unchanged %s", target)
            write_lineage(
                dest_dir,
                {
                    "source_id": source_id,
                    "url": url,
                    "retrieved_at": utc_now_iso(),
                    "ok": True,
                    "http_status": status,
                    "path": str(target.relative_to(dest_dir.parent.parent.parent)
                    if dest_dir.parts
                    else target),
                    "sha256": digest,
                    "bytes": len(content),
                    "skipped": True,
                    "license_note": license_note,
                    "content_type": headers.get("content-type"),
                },
            )
            return target
        stem, suffix = target.stem, target.suffix
        target = dest_dir / f"{stem}_{digest[:10]}{suffix}"

    target.write_bytes(content)
    write_lineage(
        dest_dir,
        {
            "source_id": source_id,
            "url": url,
            "retrieved_at": utc_now_iso(),
            "ok": True,
            "http_status": status,
            "path": str(target),
            "sha256": digest,
            "bytes": len(content),
            "skipped": False,
            "license_note": license_note,
            "content_type": headers.get("content-type"),
        },
    )
    logger.info("Saved %s (%s bytes)", str(target).encode("ascii", "replace").decode("ascii"), len(content))
    return target


def raw_run_dir(base: Path, source_id: str, as_of: str | None = None) -> Path:
    day = as_of or utc_today()
    path = base / source_id / day
    path.mkdir(parents=True, exist_ok=True)
    return path