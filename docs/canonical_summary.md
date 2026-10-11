# Canonical Dataset Summary

End-user-ready annual aggregates after cleaning.

## Snapshot

- Rows: **182**
- Years: **2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023**
- Quality tiers: `{'B': 156, 'A': 21, 'C': 5}`
- Completeness: `{'category_detail': 177, 'total_only': 5}`
- City detail ≤ total: **PASS**

## Bengaluru City annual totals

| Year | Reported cases | Tier | Completeness | Source |
| --- | ---: | --- | --- | --- |
| 2012 | 2263 | C | total_only | ncrb_caw_backfill_2012_2016 |
| 2013 | 2608 | C | total_only | ncrb_caw_backfill_2012_2016 |
| 2014 | 3100 | C | total_only | ncrb_caw_backfill_2012_2016 |
| 2015 | 3109 | C | total_only | ncrb_caw_backfill_2012_2016 |
| 2016 | 3412 | C | total_only | ncrb_caw_backfill_2012_2016 |
| 2021 | 2020 | A | category_detail | opencity_bengaluru_crime_2023 |
| 2022 | 2630 | A | category_detail | opencity_bengaluru_crime_2023 |
| 2023 | 3260 | A | category_detail | opencity_bengaluru_crime_2023 |

## Bengaluru City coverage by year

| Year | Categories | Has total | Detail sum |
| --- | ---: | --- | ---: |
| 2012 | 1 | yes (2263) | 0 |
| 2013 | 1 | yes (2608) | 0 |
| 2014 | 1 | yes (3100) | 0 |
| 2015 | 1 | yes (3109) | 0 |
| 2016 | 1 | yes (3412) | 0 |
| 2017 | 9 | no | 3371 |
| 2018 | 9 | no | 3274 |
| 2019 | 9 | no | 3311 |
| 2020 | 9 | no | 2612 |
| 2021 | 7 | yes (2020) | 2020 |
| 2022 | 7 | yes (2630) | 2630 |
| 2023 | 7 | yes (3260) | 3260 |

## Believability rules applied

1. Only count metrics (`reported` / `incidents`) enter the product table.
2. Junk labels (`col_*`, indexes, subtotals) dropped.
3. Taxonomy remapped (SH subtypes, Voyeurism, Insult to modesty, etc.).
4. IDP uses exclusive primary columns only (no overlapping POCSO/rape heads).
5. Broken NCRB category packs where a head exceeds Total are dropped.
6. When a year has an official Total, only that source's categories are shown.
7. Statewide Karnataka tables are never labeled as Bengaluru City.
8. Thin years flagged `total_only` / tier `C` so UI can avoid overclaiming.

See also: [data_dictionary.md](data_dictionary.md)
