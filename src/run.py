"""Build the dashboard data files.

    python src/run.py            # live: pulls from the Census API (set CENSUS_API_KEY)
    python src/run.py --sample   # offline: uses tests/sample data
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import analysis  # noqa: E402

OUT = ROOT / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    if args.sample:
        hs2 = pd.read_csv(ROOT / "tests" / "sample_hs2.csv", dtype={"hs": str})
        hs10 = pd.read_csv(ROOT / "tests" / "sample_hs10.csv", dtype={"hs": str})
    else:
        import census
        hs2 = census.fetch("HS2", start="2019-01")
        hs10 = census.fetch("HS10", start="2024-01")

    latest = hs2["period"].max()
    series = analysis.monthly_series(hs2)
    breakdown = {}
    for mode in ("yoy", "mom", "ytd"):
        res = analysis.drivers(hs2, latest, mode)
        res["read_en"] = analysis.read(res, "en")
        res["read_es"] = analysis.read(res, "es")
        breakdown[mode] = res

    OUT.mkdir(exist_ok=True)
    (OUT / "deficit.json").write_text(json.dumps({
        "latest": latest,
        "series": json.loads(series.to_json(orient="records")),
        "breakdown": breakdown,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "s232.json").write_text(json.dumps(analysis.s232(hs10), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"latest {latest}: {breakdown['yoy']['read_en']}")


if __name__ == "__main__":
    main()
