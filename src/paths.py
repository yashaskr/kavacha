"""Project path helpers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = ROOT / "catalogs"
SOURCES_YAML = CATALOGS / "sources.yaml"
DATA = ROOT / "data"
RAW = DATA / "raw"
STAGING = DATA / "staging"
REFERENCE = DATA / "reference"
DOCS = ROOT / "docs"


def ensure_data_dirs() -> None:
    for path in (RAW, STAGING, REFERENCE, DOCS):
        path.mkdir(parents=True, exist_ok=True)