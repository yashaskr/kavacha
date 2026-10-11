"""Geographic alias normalization for Bengaluru / Karnataka units."""

from __future__ import annotations

import re

# Canonical names used in staging
CANONICAL = {
    "bengaluru_city": {
        "geo_level": "city",
        "geo_name": "Bengaluru City",
        "aliases": [
            "bengaluru",
            "bengaluru city",
            "bangalore",
            "bangalore city",
            "bengaluru city police",
            "bcp",
            "bbmp",
            "bengaluru commissionerate",
            "commissionerate bengaluru city",
        ],
    },
    "bengaluru_district": {
        "geo_level": "district",
        "geo_name": "Bengaluru District",
        "aliases": [
            "bengaluru dist",
            "bengaluru district",
            "bangalore district",
            "bangalore rural",
            "bengaluru rural",
        ],
    },
    "bengaluru_urban": {
        "geo_level": "district",
        "geo_name": "Bengaluru Urban",
        "aliases": [
            "bengaluru urban",
            "bangalore urban",
        ],
    },
    "bengaluru_railways": {
        "geo_level": "city",
        "geo_name": "Bengaluru Railways",
        "aliases": [
            "k.railways",
            "k railways",
            "bengaluru railways",
            "bangalore railways",
            "railway bengaluru",
        ],
    },
    "bengaluru_south": {
        "geo_level": "district",
        "geo_name": "Bengaluru South",
        "aliases": ["bengaluru south", "bangalore south"],
    },
    "karnataka": {
        "geo_level": "state",
        "geo_name": "Karnataka",
        "aliases": ["karnataka", "state", "ka"],
    },
}


def _norm(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[\./,]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def resolve_geo(name: str | None) -> tuple[str | None, str | None, float]:
    """Return (geo_level, geo_name, confidence) or (None, original, 0) if unknown."""
    if name is None:
        return None, None, 0.0
    raw = str(name).strip()
    key = _norm(raw)
    if not key:
        return None, None, 0.0

    # Exact alias match
    for meta in CANONICAL.values():
        if key in meta["aliases"] or key == _norm(meta["geo_name"]):
            return meta["geo_level"], meta["geo_name"], 0.95

    # Fuzzy contains for Bengaluru city commissionerate rows
    if "bengaluru city" in key or "bangalore city" in key:
        return "city", "Bengaluru City", 0.9
    if key in {"bengaluru", "bangalore"}:
        return "city", "Bengaluru City", 0.7
    if "bengaluru" in key or "bangalore" in key:
        if "south" in key:
            return "district", "Bengaluru South", 0.85
        if "rural" in key or "dist" in key or "district" in key:
            return "district", "Bengaluru District", 0.85
        if "urban" in key:
            return "district", "Bengaluru District", 0.6
        return "city", "Bengaluru City", 0.55

    return None, raw, 0.0


def is_bengaluru_related(name: str | None) -> bool:
    level, geo, conf = resolve_geo(name)
    if conf <= 0:
        return False
    return geo is not None and "Bengaluru" in geo


def alias_table_rows() -> list[dict]:
    rows = []
    for canon_id, meta in CANONICAL.items():
        for alias in meta["aliases"]:
            rows.append(
                {
                    "canonical_id": canon_id,
                    "geo_level": meta["geo_level"],
                    "geo_name": meta["geo_name"],
                    "alias": alias,
                }
            )
    return rows