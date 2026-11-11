"""Pull series from Banxico's SIE API (token in BANXICO_TOKEN)."""
import os

import pandas as pd
import requests

BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"

# Series IDs from Banxico's catalog. The first live run checks each one; any ID that
# returns nothing is reported in data/status.json so it can be corrected.
SERIES = {
    "SF43718": {"id": "usdmxn_fix", "en": "USD/MXN (FIX)", "es": "Tipo de cambio FIX", "unit": "MXN per USD", "freq": "daily"},
    "SF61745": {"id": "policy_rate", "en": "Banxico policy rate", "es": "Tasa objetivo de Banxico", "unit": "%", "freq": "daily"},
    "SE27803": {"id": "remittances", "en": "Remittances", "es": "Remesas", "unit": "US$ mn", "freq": "monthly"},
}


def fetch(start="2019-01-01"):
    token = os.environ["BANXICO_TOKEN"]
    ids = ",".join(SERIES)
    r = requests.get(f"{BASE}/{ids}/datos/{start}/{pd.Timestamp.today():%Y-%m-%d}",
                     headers={"Bmx-Token": token, "Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    out, missing = {}, []
    found = {s["idSerie"]: s for s in r.json()["bmx"]["series"]}
    for sid, meta in SERIES.items():
        rows = found.get(sid, {}).get("datos") or []
        if not rows:
            missing.append(sid)
            continue
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y")
        df["value"] = pd.to_numeric(df["dato"].str.replace(",", ""), errors="coerce")
        df = df.dropna(subset=["value"])[["date", "value"]]
        out[meta["id"]] = {**meta, "series_id": sid, "title_banxico": found[sid].get("titulo"),
                           "data": [{"date": d.strftime("%Y-%m-%d"), "value": v} for d, v in zip(df["date"], df["value"])]}
    return out, missing


def latest_summary(series):
    """Latest value and simple changes for each series."""
    summary = {}
    for key, s in series.items():
        df = pd.DataFrame(s["data"])
        df["date"] = pd.to_datetime(df["date"])
        last = df.iloc[-1]
        year_ago = df[df["date"] <= last["date"] - pd.DateOffset(years=1)]
        summary[key] = {
            "en": s["en"], "es": s["es"], "unit": s["unit"],
            "date": last["date"].strftime("%Y-%m-%d"), "value": float(last["value"]),
            "prev": float(df.iloc[-2]["value"]) if len(df) > 1 else None,
            "year_ago": float(year_ago.iloc[-1]["value"]) if len(year_ago) else None,
        }
    return summary
