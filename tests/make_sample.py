"""Synthetic sample data so the pipeline can run offline. NOT real data by product.

Monthly totals for Sep 2025 and Sep 2026 are pinned to the published Census figures
(imports 44.58 / 62.24 bn, exports 27.22 / 34.09 bn); the product split is invented.
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
rng = np.random.default_rng(7)
periods = [str(p) for p in pd.period_range("2023-01", "2026-09", freq="M")]
imp_share = {"87": .27, "85": .22, "84": .20, "90": .04, "27": .02, "72": .015, "73": .015, "76": .01, "07": .03, "22": .02, "39": .03}
exp_share = {"27": .17, "84": .16, "85": .14, "39": .09, "87": .08, "72": .03, "73": .03, "76": .03, "10": .03, "02": .02, "90": .03}
pinned = {"2025-09": (44.58e9, 27.22e9), "2026-09": (62.24e9, 34.09e9)}

rows = []
for i, p in enumerate(periods):
    imp_tot, exp_tot = pinned.get(p, (42e9 * (1.012 ** i) * rng.uniform(.95, 1.05), 27e9 * (1.007 ** i) * rng.uniform(.95, 1.05)))
    w_i = {k: v * rng.uniform(.9, 1.1) for k, v in imp_share.items()}
    w_e = {k: v * rng.uniform(.9, 1.1) for k, v in exp_share.items()}
    for h in sorted(set(imp_share) | set(exp_share) | {"99"}):
        rows.append({"period": p, "hs": h, "imports": w_i.get(h, 0), "exports": w_e.get(h, 0)})
df = pd.DataFrame(rows)
# put the residual share into chapter 99 so totals hit the target exactly
for p in periods:
    imp_tot, exp_tot = pinned.get(p, (None, None))
    m = df["period"] == p
    si, se = df.loc[m, "imports"].sum(), df.loc[m, "exports"].sum()
    df.loc[m & (df.hs == "99"), "imports"] = max(0, 1 - si)
    df.loc[m & (df.hs == "99"), "exports"] = max(0, 1 - se)
    if imp_tot is None:
        imp_tot, exp_tot = 42e9 * (1.012 ** periods.index(p)), 27e9 * (1.007 ** periods.index(p))
    df.loc[m, "imports"] *= imp_tot / df.loc[m, "imports"].sum()
    df.loc[m, "exports"] *= exp_tot / df.loc[m, "exports"].sum()
df["duties"] = df["imports"] * 0.036
df.to_csv(HERE / "sample_hs2.csv", index=False)

hs10 = []
codes = {"7208100000": "72", "7306300000": "73", "7604100000": "76", "8703230190": "87", "8708995800": "87", "8701210000": "87", "8704230000": "87", "8471500150": "84"}
for p in periods:
    for code, ch in codes.items():
        base = df[(df.period == p) & (df.hs == ch)]["imports"].iloc[0]
        hs10.append({"period": p, "hs": code, "imports": base * rng.uniform(.1, .3), "duties": 0.0})
    hs10.append({"period": p, "hs": "9999999999", "imports": df[df.period == p]["imports"].sum() * .6, "duties": 0.0})
h = pd.DataFrame(hs10)
h["duties"] = h["imports"] * np.where(h.hs.str[:2].isin(["72", "73", "76"]), .5, .05)
h.to_csv(HERE / "sample_hs10.csv", index=False)
print("wrote sample_hs2.csv and sample_hs10.csv")
