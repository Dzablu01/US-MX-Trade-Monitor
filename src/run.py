"""Build the dashboard data files.

    python src/run.py            # live
    python src/run.py --sample   # offline, synthetic sample data

Each source runs on its own: if one fails (missing key, site down), the others still
update, and data/status.json records what happened.
"""
import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import analysis  # noqa: E402

OUT = ROOT / "data"


def write(name, obj):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def build_census(sample):
    if sample:
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
    write("deficit.json", {"latest": latest, "sample": sample,
                           "series": json.loads(series.to_json(orient="records")),
                           "breakdown": breakdown})
    write("s232.json", {**analysis.s232(hs10), "sample": sample})
    return f"latest {latest}; " + breakdown["yoy"]["read_en"]


def build_banxico(sample):
    if sample:
        return "skipped in sample mode"
    if not os.environ.get("BANXICO_TOKEN"):
        raise RuntimeError("BANXICO_TOKEN secret not set")
    import banxico
    series, missing = banxico.fetch()
    write("banxico.json", {"series": series, "summary": banxico.latest_summary(series)})
    msg = ", ".join(f"{k}={v['value']} ({v['date']}) [{v['title_banxico']}]" for k, v in banxico.latest_summary(series).items())
    return msg + (f"; series IDs with no data: {missing}" if missing else "")


def build_inegi(sample):
    if sample:
        return "skipped in sample mode"
    if not os.environ.get("INEGI_TOKEN"):
        raise RuntimeError("INEGI_TOKEN secret not set")
    import inegi
    series, problems = inegi.fetch()
    write("inegi.json", {"series": series, "problems": problems})
    msg = "; ".join(f"{s['series_id']} = \"{s['inegi_title']}\" latest {s['data'][-1]['period']}: {s['data'][-1]['value']}"
                    for s in series.values() if s["data"])
    return msg + (f"; problems: {problems}" if problems else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()
    status = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": {}}
    for name, fn in (("census", build_census), ("banxico", build_banxico), ("inegi", build_inegi)):
        try:
            status["sources"][name] = {"ok": True, "note": fn(args.sample)}
        except Exception as e:  # keep going; record the problem
            status["sources"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}",
                                       "trace": traceback.format_exc(limit=3)}
        print(name, status["sources"][name].get("note") or status["sources"][name]["error"])
    write("status.json", status)


if __name__ == "__main__":
    main()
