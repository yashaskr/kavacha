# Police-station crime layer — data spec

The Kavacha map has two modes:

1. **City pressure** — works today from `crime_annual_bengaluru_city.csv`
2. **Station detail** — needs a PS × year table (not in open NCRB/BCP city dumps)

## File the UI looks for

`web/data/geo/ps_crime.csv` (copied from staging when available)

| Column | Required | Notes |
| --- | --- | --- |
| `year` | yes | Calendar year |
| `station_name` | yes | Must fuzzy-match OpenCity `POL_STAName` / `PS_BOUNDName` (e.g. `Cubbon Park PS`) |
| `station_code` | no | Helps join (`PS - 84`, `KGISPSCode`) |
| `category` | yes | Use `Total Crimes Against Women` for the marker size; other heads optional |
| `reported_cases` | yes | Non-negative integer |
| `source_note` | no | e.g. `BCP RTI reply 2026-xx` |

Example template: `web/data/geo/ps_crime.example.csv` (not loaded by the app).

## How to obtain it

RTI to Bengaluru City Police / SCRB asking for year-wise CAW registered **by police station** (Excel preferred). See backlog in `open_data_research.md`.

## Join rule

- Match `station_name` → station point / jurisdiction polygon name (case-insensitive, strip `PS` suffix variants).
- Unmatched stations stay “no local count”.
- **Never** allocate city totals across stations to fill gaps.

## Product rule

City totals and PS counts are different grains. Show both; do not sum or average them into one misleading layer.
