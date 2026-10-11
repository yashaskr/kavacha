"""Copy canonical staging CSVs into web/data for the Kavacha UI.

Also refreshes reference GeoJSON map layers when source KMLs exist.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "staging"
DEST = ROOT / "web" / "data"
FILES = (
    "crime_annual_bengaluru_city.csv",
    "crime_annual_totals.csv",
)


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = SRC / name
        if not src.exists():
            print(f"missing {src} — run: python -m src.cli clean")
            continue
        shutil.copy2(src, DEST / name)
        print(f"synced {name}")

    prep = ROOT / "scripts" / "prepare_map_layers.py"
    if prep.exists():
        subprocess.run([sys.executable, str(prep)], check=False)

    # Optional PS-level crime (RTI/BCP) — copy if present in staging
    ps_src = SRC / "ps_crime.csv"
    ps_dest = DEST / "geo" / "ps_crime.csv"
    if ps_src.exists():
        ps_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ps_src, ps_dest)
        print("synced ps_crime.csv")
    else:
        print("no staging/ps_crime.csv (station map mode waits for RTI/BCP file)")


if __name__ == "__main__":
    main()
