"""Pull series from INEGI's indicator API (token in INEGI_TOKEN).

Series IDs below are CANDIDATES. Each run also fetches INEGI's own title for every ID
and records it in data/inegi.json, so wrong IDs are easy to spot and replace.
"""
import os

import requests

BASE = "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml"

CANDIDATES = {
    "628229": {"id": "inpc", "en": "Inflation (INPC)", "es": "Inflación (INPC)"},
    "737121": {"id": "igae", "en": "IGAE (monthly activity)", "es": "IGAE (actividad mensual)"},
    "444612": {"id": "unemployment", "en": "Unemployment rate", "es": "Tasa de desocupación"},
}


def _get(path):
    r = requests.get(f"{BASE}/{path}/{os.environ['INEGI_TOKEN']}?type=json", timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"INEGI HTTP {r.status_code}: {r.text[:300]!r}")
    return r.json()


def title(series_id):
    try:
        codes = _get(f"CL_INDICATOR/{series_id}/es/BIE/2.0")["CODE"]
        return codes[0].get("Description") if codes else None
    except Exception as e:
        return f"(title lookup failed: {e})"


def fetch():
    out, problems = {}, []
    for sid, meta in CANDIDATES.items():
        try:
            series = _get(f"INDICATOR/{sid}/es/00/false/BIE/2.0")["Series"][0]
            obs = [{"period": o["TIME_PERIOD"], "value": float(o["OBS_VALUE"])}
                   for o in series["OBSERVATIONS"] if o.get("OBS_VALUE") not in (None, "")]
            obs.sort(key=lambda o: o["period"])
            out[meta["id"]] = {**meta, "series_id": sid, "inegi_title": title(sid),
                               "freq": series.get("FREQ"), "unit": series.get("UNIT"), "data": obs}
        except Exception as e:
            problems.append(f"{sid} ({meta['en']}): {type(e).__name__}: {e}")
    return out, problems
