"""Pull series from INEGI's indicator API (token in INEGI_TOKEN).

Series IDs below are CANDIDATES. Each run also fetches INEGI's own title for every ID
and records it in data/inegi.json, so wrong IDs are easy to spot and replace.
"""
import os

import requests

BASE = "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml"

# INEGI's sources are now "BIE-BISE" and "BISE" (the old "BIE" source was retired), and
# national data may be geography "00" or "0700". Each candidate ID is tried against every
# combination; the first that returns data wins and is recorded.
SOURCES = ["BIE-BISE", "BISE"]
GEOS = ["0700", "00"]
PROBE = "1002000001"  # total population (BISE): the documented example, used to test the token/format

CANDIDATES = {
    "inpc": {"en": "Inflation (INPC)", "es": "Inflación (INPC)", "ids": ["628194", "628229", "910392"]},
    "igae": {"en": "IGAE (monthly activity)", "es": "IGAE (actividad mensual)", "ids": ["737121", "736939", "496150"]},
    "unemployment": {"en": "Unemployment rate", "es": "Tasa de desocupación", "ids": ["444612", "444884", "6200093973"]},
}


def _get(path):
    r = requests.get(f"{BASE}/{path}/{os.environ['INEGI_TOKEN']}?type=json", timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"INEGI HTTP {r.status_code}: {r.text[:300]!r}")
    return r.json()


def title(series_id, source):
    try:
        codes = _get(f"CL_INDICATOR/{series_id}/es/{source}/2.0")["CODE"]
        return codes[0].get("Description") if codes else None
    except Exception as e:
        return f"(title lookup failed: {e})"


def _try(sid):
    errors = []
    for src in SOURCES:
        for geo in GEOS:
            try:
                series = _get(f"INDICATOR/{sid}/es/{geo}/false/{src}/2.0")["Series"][0]
                return series, src, geo, errors
            except Exception as e:
                errors.append(f"{src}/{geo}: {str(e)[:80]}")
    return None, None, None, errors


def fetch():
    out, problems = {}, []
    probe, src, geo, errs = _try(PROBE)
    problems.append(f"probe {PROBE}: " + (f"OK via {src}/{geo}" if probe else f"FAILED {errs}"))
    for key, meta in CANDIDATES.items():
        for sid in meta["ids"]:
            series, src, geo, errs = _try(sid)
            if not series:
                problems.append(f"{key} {sid}: no data ({errs[-1] if errs else ''})")
                continue
            obs = [{"period": o["TIME_PERIOD"], "value": float(o["OBS_VALUE"])}
                   for o in series["OBSERVATIONS"] if o.get("OBS_VALUE") not in (None, "")]
            obs.sort(key=lambda o: o["period"])
            out[key] = {"en": meta["en"], "es": meta["es"], "series_id": sid, "source": src, "geo": geo,
                        "inegi_title": title(sid, src), "freq": series.get("FREQ"),
                        "unit": series.get("UNIT"), "data": obs}
            break
    return out, problems
