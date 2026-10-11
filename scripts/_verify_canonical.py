"""Verify canonical outputs after clean."""
from pathlib import Path

import pandas as pd

root = Path(r"c:\Users\user\Downloads\women-safety-project\data\staging")
city = pd.read_csv(root / "crime_annual_bengaluru_city.csv")
totals = pd.read_csv(root / "crime_annual_totals.csv")
can = pd.read_csv(root / "crime_annual_canonical.csv")

print("=== CITY TOTALS ===")
t = city[city.crime_category_normalized == "Total Crimes Against Women"].sort_values("year")
print(
    t[["year", "value", "source_id", "quality_tier", "completeness"]].to_string(index=False)
)

expected = {2012: 2263, 2013: 2608, 2014: 3100, 2015: 3109, 2016: 3412, 2021: 2020, 2022: 2630, 2023: 3260}
print("\n=== EXPECTED TOTAL CHECK ===")
for y, exp in expected.items():
    row = t[t.year == y]
    got = int(row["value"].iloc[0]) if len(row) else None
    print(f"{y}: got={got} expected={exp} {'OK' if got == exp else 'MISMATCH'}")

print("\n=== CITY: sum(detail) vs Total ===")
ok = True
for year, grp in city.groupby("year"):
    total_row = grp[grp.crime_category_normalized == "Total Crimes Against Women"]
    detail = grp[grp.crime_category_normalized != "Total Crimes Against Women"]
    total = float(total_row["value"].iloc[0]) if len(total_row) else None
    detail_sum = float(detail["value"].sum()) if len(detail) else 0.0
    ratio_ok = total is None or detail_sum <= total + 1
    if not ratio_ok:
        ok = False
    print(
        f"{year}: total={total} detail_sum={detail_sum:.0f} n={len(detail)} "
        f"{'OK' if ratio_ok else 'FAIL'} sources={sorted(detail.source_id.unique().tolist() + total_row.source_id.unique().tolist())}"
    )

print("\n=== NO STATE-AS-CITY 2024/25 ===")
bad = city[(city.year.isin([2024, 2025])) & (city.value > 2000)]
print("inflated rows:", len(bad))
if len(bad):
    print(bad.to_string(index=False))

print("\n=== ROWS ===")
print("canonical", len(can), "city", len(city), "totals", len(totals))
print("city_detail_ok", ok)
print("dups", int(can.duplicated(subset=["year", "geo_name", "crime_category_normalized"], keep=False).sum()))
