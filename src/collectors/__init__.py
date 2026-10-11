"""Source collectors."""

from __future__ import annotations

from src.collectors import (
    data_gov_in,
    gis_github,
    india_data_portal,
    ncrb_backfill,
    ncrb_pdf,
    opencity,
)
from src.collectors.base import CollectResult, summarize


def collect(source_family: str | None = None) -> list[CollectResult]:
    """Run collectors. source_family filters to one family when provided."""
    results: list[CollectResult] = []

    runners = {
        "opencity": lambda: opencity.collect_all(["opencity"]),
        "gis_opencity": lambda: opencity.collect_all(["gis_opencity"]),
        "india_data_portal": india_data_portal.collect_all,
        "data_gov_in": data_gov_in.collect_all,
        "ncrb_pdf": ncrb_pdf.collect_all,
        "ncrb_backfill": ncrb_backfill.collect_all,
        "gis_github": gis_github.collect_all,
    }

    if source_family:
        key = source_family.strip().lower()
        if key not in runners:
            raise ValueError(f"Unknown source family: {source_family}. Choose from {list(runners)}")
        return runners[key]()

    for name, runner in runners.items():
        results.extend(runner())
    return results


__all__ = ["collect", "CollectResult", "summarize"]