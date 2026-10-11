"""Load machine-readable source inventory."""

from __future__ import annotations

from typing import Any

import yaml

from src.paths import SOURCES_YAML


def load_sources() -> dict[str, Any]:
    with SOURCES_YAML.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sources_by_family(family: str | None = None, tier: str | None = None) -> list[dict[str, Any]]:
    data = load_sources()
    items = data.get("sources", [])
    if family:
        items = [s for s in items if s.get("family") == family]
    if tier:
        items = [s for s in items if str(s.get("tier")) == tier]
    return items


def source_by_id(source_id: str) -> dict[str, Any] | None:
    for item in load_sources().get("sources", []):
        if item.get("id") == source_id:
            return item
    return None