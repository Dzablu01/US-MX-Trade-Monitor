# US–Mexico Trade Monitor

Trade, data and policy signals for the U.S.–Mexico relationship.

## What's here (first build)

- `src/census.py` pulls U.S. goods trade with Mexico (Census country code 2010): imports, calculated duties and exports, by HS chapter and HS-10.
- `src/analysis.py` builds:
  - the monthly deficit series and 12-month average;
  - the breakdown of what moved the deficit (vs a year earlier, vs last month, year to date), by product group;
  - a one-paragraph read in English and Spanish;
  - imports from Mexico and duties under Section 232 (steel, aluminum, autos and parts, medium and heavy trucks).
- `config/product_groups.json` maps HS chapters to the groups.
- `config/s232_scope.json` lists the tariff codes counted under each Section 232 category. **It's a starter list**: replace it with the official HTS-10 lists before relying on the numbers.
- `.github/workflows/update.yml` runs everything three times each weekday and saves the results to `data/`.

## Setup

1. In the repository on GitHub, go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   `CENSUS_API_KEY`, `BANXICO_TOKEN`, `INEGI_TOKEN`, `ANTHROPIC_API_KEY`.
2. Go to **Actions → Update data → Run workflow** to run it once by hand.

## Run locally

```
pip install -r requirements.txt
python tests/make_sample.py      # synthetic sample data
python -m pytest -q tests
python src/run.py --sample       # offline run
CENSUS_API_KEY=... python src/run.py   # live run
```

Sample data is synthetic by product. Only the September 2025 and September 2026 totals match the published Census figures.

## Next

Banxico and INEGI indicators, the alert engine (email first, then WhatsApp), the news feed, and the live dashboard page.
