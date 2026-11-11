import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import analysis  # noqa: E402

df = pd.read_csv(ROOT / "tests" / "sample_hs2.csv", dtype={"hs": str})


def test_yoy_matches_published_totals():
    r = analysis.drivers(df, "2026-09", "yoy")
    t = r["totals"]
    assert t["deficit_cur_bn"] == 28.15
    assert t["deficit_base_bn"] == 17.36
    assert t["d_imports_bn"] == 17.66 and t["d_exports_bn"] == 6.87
    assert abs(sum(g["contribution_bn"] for g in r["groups"]) - t["d_balance_bn"]) < 0.05


def test_modes_and_reads():
    for mode in ("yoy", "mom", "ytd"):
        r = analysis.drivers(df, "2026-09", mode)
        assert analysis.read(r, "en") and analysis.read(r, "es")


def test_s232_runs():
    h = pd.read_csv(ROOT / "tests" / "sample_hs10.csv", dtype={"hs": str})
    out = analysis.s232(h)
    assert {c["id"] for c in out["categories"]} == {"steel", "aluminum", "autos", "trucks"}
    assert all(c["series"] for c in out["categories"])
