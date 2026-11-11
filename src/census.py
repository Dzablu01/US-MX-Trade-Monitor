"""Pull U.S. goods trade with Mexico from the Census international trade API.

Imports: general imports value (GEN_VAL_MO) and calculated duties (CAL_DUT_MO).
Exports: total exports value (ALL_VAL_MO).
Country code 2010 = Mexico. Values are in U.S. dollars, not seasonally adjusted.

Downloads one month per request and caches each month in data/raw/. Months older than
REFRESH_MONTHS are reused from the cache; recent months are re-downloaded each run
because Census revises them.
"""
import os
import time
from pathlib import Path

import pandas as pd
import requests

BASE = "https://api.census.gov/data/timeseries/intltrade"
MEXICO = "2010"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
REFRESH_MONTHS = 14


def _get(url, params, retries=4):
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        params = {**params, "key": key.strip()}
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=180)
        except requests.RequestException as e:
            last = e
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 200:
            try:
                rows = r.json()
            except ValueError:
                raise RuntimeError(f"Census returned non-JSON (HTTP 200) for {r.url.split('key=')[0]}: {r.text[:300]!r}")
            return pd.DataFrame(rows[1:], columns=rows[0])
        if r.status_code == 204:  # no data for that query (e.g. month not released yet)
            return pd.DataFrame()
        if r.status_code in (400, 401, 403):
            raise RuntimeError(f"Census HTTP {r.status_code}: {r.text[:300]!r}")
        last = RuntimeError(f"Census HTTP {r.status_code}")
        time.sleep(5 * (attempt + 1))
    raise last


def _month(level, period, with_exports=True):
    imp = _get(f"{BASE}/imports/hs", {"get": "I_COMMODITY,GEN_VAL_MO,CAL_DUT_MO",
                                      "CTY_CODE": MEXICO, "COMM_LVL": level, "time": period})
    if imp.empty:
        return pd.DataFrame()
    imp = imp.rename(columns={"I_COMMODITY": "hs", "GEN_VAL_MO": "imports", "CAL_DUT_MO": "duties"})
    df = imp[["hs", "imports", "duties"]]
    if with_exports:
        exp = _get(f"{BASE}/exports/hs", {"get": "E_COMMODITY,ALL_VAL_MO",
                                          "CTY_CODE": MEXICO, "COMM_LVL": level, "time": period})
        if not exp.empty:
            exp = exp.rename(columns={"E_COMMODITY": "hs", "ALL_VAL_MO": "exports"})[["hs", "exports"]]
            df = df.merge(exp, on="hs", how="outer")
    for c in ("imports", "duties", "exports"):
        if c not in df:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df = df.groupby("hs", as_index=False)[["imports", "duties", "exports"]].sum()
    df.insert(0, "period", period)
    return df


def fetch(level="HS2", start="2019-01", with_exports=True):
    """One row per (period, hs code) with imports, duties and exports in US$."""
    RAW.mkdir(parents=True, exist_ok=True)
    today = pd.Period(pd.Timestamp.today(), freq="M")
    frames = []
    for p in pd.period_range(start, today - 1, freq="M"):
        path = RAW / f"{level.lower()}_{p}.csv"
        fresh = (today - p).n > REFRESH_MONTHS
        if fresh and path.exists():
            frames.append(pd.read_csv(path, dtype={"hs": str}))
            continue
        try:
            df = _month(level, str(p), with_exports)
        except RuntimeError:
            if (today - p).n <= 2:  # newest months may not be published yet
                continue
            raise
        if df.empty:
            continue  # not released yet
        df.to_csv(path, index=False)
        frames.append(df)
    if not frames:
        raise RuntimeError("Census returned no months")
    return pd.concat(frames, ignore_index=True).sort_values(["period", "hs"]).reset_index(drop=True)
