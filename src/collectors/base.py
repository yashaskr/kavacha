"""Collector protocol helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CollectResult:
    source_id: str
    ok: bool
    files: list[str] = field(default_factory=list)
    error: str | None = None
    message: str = ""


def summarize(results: list[CollectResult]) -> dict[str, Any]:
    return {
        "total": len(results),
        "ok": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if not r.ok),
        "files": sum(len(r.files) for r in results),
        "results": [r.__dict__ for r in results],
    }