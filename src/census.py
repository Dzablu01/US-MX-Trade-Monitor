"""Pull U.S. goods trade with Mexico from the Census international trade API.

Imports: general imports value (GEN_VAL_MO) and calculated duties (CAL_DUT_MO).
Exports: total exports value (ALL_VAL_MO).
Country code 2010 = Mexico. Values are in U.S. dollars, not seasonally adjusted.
"""
import os
import time

import pandas as pd
import requests

BASE = "https://api.census.gov/data/timeseries/intltrade"
MEXICO = "2010"


def _get(url, params, retries=3):
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        params = {**params, "key": key}
    for attempt in range(retries):
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 200:
            rows = r.json()
            return pd.DataFrame(rows[1:], columns=rows[0])
        if r.status_code == 204:  # no data for that query
            return pd.DataFrame()
        time.sleep(2 ** attempt)
    r.raise_for_status()


def fetch(level="HS2", start="2019-01"):
    """Return one row per (period, hs code) with imports, duties and exports in US$."""
    imp = _get(f"{BASE}/imports/hs", {
        "get": "I_COMMODITY,GEN_VAL_MO,CAL_DUT_MO",
        "CTY_CODE": MEXICO, "COMM_LVL": level, "time": f"from {start}",
    }).rename(columns={"I_COMMODITY": "hs", "GEN_VAL_MO": "imports", "CAL_DUT_MO": "duties"})
    exp = _get(f"{BASE}/exports/hs", {
        "get": "E_COMMODITY,ALL_VAL_MO",
        "CTY_CODE": MEXICO, "COMM_LVL": level, "time": f"from {start}",
    }).rename(columns={"E_COMMODITY": "hs", "ALL_VAL_MO": "exports"})
    for df in (imp, exp):
        df.rename(columns={"time": "period"}, inplace=True)
        df.drop(columns=[c for c in ("CTY_CODE", "COMM_LVL") if c in df.columns], inplace=True)
    df = imp.merge(exp, on=["period", "hs"], how="outer")
    for c in ("imports", "duties", "exports"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df.sort_values(["period", "hs"]).reset_index(drop=True)
