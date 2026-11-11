"""Deficit breakdown and Section 232 tracking.

Input frame columns: period ('YYYY-MM'), hs (string code), imports, exports, duties (US$).
"""
import json
from pathlib import Path

import pandas as pd

CONFIG = Path(__file__).resolve().parent.parent / "config"
BN = 1e9


def load_json(name):
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


# ---------- monthly series ----------

def monthly_series(df):
    m = df.groupby("period")[["imports", "exports", "duties"]].sum().reset_index()
    m["balance"] = m["exports"] - m["imports"]
    m["deficit"] = -m["balance"]
    m["deficit_12m_avg"] = m["deficit"].rolling(12, min_periods=12).mean()
    return m


# ---------- what moved the deficit ----------

def _group_of(hs2, groups):
    for g in groups:
        if hs2 in g["hs2"]:
            return g["id"]
    return "other"


def _shift(period, months):
    p = pd.Period(period, freq="M") + months
    return str(p)


def _window(df, end, mode):
    """Periods for the current window and the comparison window."""
    if mode == "yoy":
        return [end], [_shift(end, -12)]
    if mode == "mom":
        return [end], [_shift(end, -1)]
    if mode == "ytd":
        year, month = end.split("-")
        cur = [f"{year}-{m:02d}" for m in range(1, int(month) + 1)]
        base = [f"{int(year) - 1}-{m:02d}" for m in range(1, int(month) + 1)]
        return cur, base
    raise ValueError(mode)


def drivers(df, end, mode="yoy"):
    """Contribution of each product group to the change in the balance.

    contribution = change in exports - change in imports.
    Negative contribution = widened the deficit.
    """
    groups = load_json("product_groups.json")["groups"]
    d = df.copy()
    d["group"] = d["hs"].str[:2].map(lambda h: _group_of(h, groups))
    cur_p, base_p = _window(d, end, mode)
    missing = sorted(set(cur_p + base_p) - set(d["period"]))
    if missing:
        raise ValueError(f"missing periods: {missing}")
    agg = lambda ps: d[d["period"].isin(ps)].groupby("group")[["imports", "exports"]].sum()
    cur, base = agg(cur_p), agg(base_p)
    out = cur.join(base, lsuffix="_cur", rsuffix="_base", how="outer").fillna(0.0)
    out["d_imports"] = out["imports_cur"] - out["imports_base"]
    out["d_exports"] = out["exports_cur"] - out["exports_base"]
    out["contribution"] = out["d_exports"] - out["d_imports"]
    names = {g["id"]: g for g in groups}
    rows = []
    for gid, r in out.iterrows():
        rows.append({
            "id": gid, "en": names[gid]["en"], "es": names[gid]["es"],
            "d_imports_bn": round(r["d_imports"] / BN, 2),
            "d_exports_bn": round(r["d_exports"] / BN, 2),
            "contribution_bn": round(r["contribution"] / BN, 2),
        })
    rows.sort(key=lambda x: x["contribution_bn"])  # biggest wideners first
    tot = {k: round(out[c].sum() / BN, 2) for k, c in
           (("d_imports_bn", "d_imports"), ("d_exports_bn", "d_exports"), ("d_balance_bn", "contribution"))}
    imp_cur, imp_base = out["imports_cur"].sum(), out["imports_base"].sum()
    exp_cur, exp_base = out["exports_cur"].sum(), out["exports_base"].sum()
    tot["imports_pct"] = round(100 * (imp_cur / imp_base - 1), 1) if imp_base else None
    tot["exports_pct"] = round(100 * (exp_cur / exp_base - 1), 1) if exp_base else None
    tot["deficit_cur_bn"] = round((imp_cur - exp_cur) / BN, 2)
    tot["deficit_base_bn"] = round((imp_base - exp_base) / BN, 2)
    return {"mode": mode, "end": end, "current": cur_p, "base": base_p, "totals": tot, "groups": rows}


# ---------- auto-written read, EN and ES ----------

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
             "septiembre", "octubre", "noviembre", "diciembre"]


def _label(period, lang):
    p = pd.Period(period, freq="M")
    return f"{MONTHS_ES[p.month - 1]} de {p.year}" if lang == "es" else p.strftime("%B %Y")


def _money(x):
    return f"${abs(x):.1f} bn"


def read(res, lang="en"):
    t, g = res["totals"], res["groups"]
    widened = t["d_balance_bn"] < 0
    base = {"yoy": _label(res["base"][0], lang), "mom": _label(res["base"][0], lang),
            "ytd": None}[res["mode"]]
    top = [x for x in g if x["contribution_bn"] < 0][:2] if widened else [x for x in g[::-1] if x["contribution_bn"] > 0][:2]
    offset = [x for x in g[::-1] if x["contribution_bn"] > 0][:1] if widened else [x for x in g if x["contribution_bn"] < 0][:1]
    if lang == "es":
        verb = "se amplió" if widened else "se redujo"
        when = f"respecto a {base}" if base else "en lo que va del año frente al mismo periodo del año anterior"
        s = (f"El déficit de EE.UU. con México {verb} {_money(t['d_balance_bn']).replace('bn', 'mmd')} {when}. "
             f"Las importaciones desde México variaron {t['d_imports_bn']:+.1f} mmd ({t['imports_pct']:+.1f}%) "
             f"y las exportaciones de EE.UU. {t['d_exports_bn']:+.1f} mmd ({t['exports_pct']:+.1f}%).")
        if top:
            s += " Principales factores: " + "; ".join(f"{x['es'].lower()} ({x['contribution_bn']:+.1f} mmd)" for x in top) + "."
        if offset:
            s += f" Compensado en parte por {offset[0]['es'].lower()} ({offset[0]['contribution_bn']:+.1f} mmd)."
        return s
    verb = "widened" if widened else "narrowed"
    when = f"from {base}" if base else "year to date versus the same months last year"
    s = (f"The U.S. deficit with Mexico {verb} by {_money(t['d_balance_bn'])} {when}. "
         f"Imports from Mexico changed {t['d_imports_bn']:+.1f} bn ({t['imports_pct']:+.1f}%) "
         f"and U.S. exports {t['d_exports_bn']:+.1f} bn ({t['exports_pct']:+.1f}%).")
    if top:
        s += " Main drivers: " + "; ".join(f"{x['en'].lower()} ({x['contribution_bn']:+.1f} bn)" for x in top) + "."
    if offset:
        s += f" Partly offset by {offset[0]['en'].lower()} ({offset[0]['contribution_bn']:+.1f} bn)."
    return s


# ---------- Section 232 ----------

def _match(code, cat):
    if any(code.startswith(p) for p in cat.get("exclude", [])):
        return False
    return any(code.startswith(p) for p in cat["prefixes"])


def s232(df_hs10):
    """Monthly imports from Mexico and duties per Section 232 category (needs HS-10 rows)."""
    scope = load_json("s232_scope.json")
    out = []
    for cat in scope["categories"]:
        sub = df_hs10[df_hs10["hs"].map(lambda c: _match(c, cat))]
        m = sub.groupby("period")[["imports", "duties"]].sum().reset_index()
        total = df_hs10.groupby("period")["imports"].sum()
        m["share_pct"] = (100 * m["imports"] / m["period"].map(total)).round(1)
        m["yoy_pct"] = (100 * (m["imports"] / m["imports"].shift(12) - 1)).round(1)
        out.append({
            "id": cat["id"], "en": cat["en"], "es": cat["es"], "rate": cat["rate"],
            "series": [{"period": r.period, "imports_bn": round(r.imports / BN, 3),
                        "duties_mn": round(r.duties / 1e6, 1), "share_pct": r.share_pct,
                        "yoy_pct": None if pd.isna(r.yoy_pct) else r.yoy_pct} for r in m.itertuples()],
        })
    return {"as_of": scope["as_of"], "categories": out}
