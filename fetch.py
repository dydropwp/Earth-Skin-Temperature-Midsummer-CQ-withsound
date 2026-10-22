# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///

"""
Fetch hourly Earth Skin Temperature (TS) from NASA POWER for Chongqing,
August 2026.

One request, one cache file, one CSV. The second run reads the cache and
never touches the network.

Run:
    uv run fetch.py
"""

import csv
import datetime as dt
import json
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# The knobs.
# ---------------------------------------------------------------------------

LAT, LNG = 29.56, 106.55          # Chongqing, Yuzhong district
START = "20260801"                 # YYYYMMDD
END = "20260831"                   # YYYYMMDD
PARAMETER = "TS"                   # Earth Skin Temperature
COMMUNITY = "RE"                   # Renewable Energy community

HERE = Path(__file__).parent
CACHE = HERE / "data"       # raw replies, one file per request
OUTPUT = HERE / "data" / "ts-chongqing-2026-08.csv"

URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"

# ---------------------------------------------------------------------------
# Getting the data. Fetch once, keep the file, parse the file.
# ---------------------------------------------------------------------------


def request_params():
    """The one request we need: one point, one month."""
    return {
        "parameters": PARAMETER,
        "community": COMMUNITY,
        "longitude": LNG,
        "latitude": LAT,
        "start": START,
        "end": END,
        "format": "JSON",
    }


def cache_path(params):
    """Where this request's raw reply lives."""
    return CACHE / (
        f"ts-{params['latitude']}-{params['longitude']}"
        f"-{params['start']}-{params['end']}.json"
    )


def fetch(params):
    """Return the raw JSON text. Read cache if present, else request."""
    cached = cache_path(params)

    if cached.exists():
        print(f"  cache hit: {cached.name}")
        return cached.read_text(encoding="utf-8")

    print(f"  fetching from {URL} ...")
    try:
        reply = requests.get(URL, params=params, timeout=60)
        reply.raise_for_status()
    except requests.RequestException as problem:
        print(f"  could not fetch ({problem})")
        return None

    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(reply.text, encoding="utf-8")
    print(f"  fetched and cached: {cached.name}")
    time.sleep(0.5)
    return reply.text


def markers(text, params):
    """Pull one row per hour out of one NASA POWER Feature."""
    data = json.loads(text)

    lng, lat, *_ = data["geometry"]["coordinates"]
    fill = data["header"]["fill_value"]
    series = data["properties"]["parameter"][params["parameters"]]

    rows = []
    for stamp, value in series.items():       # stamp like "2026080100"
        if value == fill:                     # skip missing values
            continue
        moment = dt.datetime.strptime(stamp, "%Y%m%d%H")
        rows.append({
            "time": moment.strftime("%Y-%m-%d %H:%M"),
            "point_id": f"{lat}_{lng}",
            "lng": round(lng, 5),
            "lat": round(lat, 5),
            "ts": float(value),
        })
    return rows


def main():
    all_rows = []
    for params in [request_params()]:
        text = fetch(params)
        if text is None:
            continue
        rows = markers(text, params)
        print(f"  {params['latitude']},{params['longitude']}  {len(rows)} values")
        all_rows.extend(rows)

    if not all_rows:
        print("nothing fetched and nothing cached — output left as it is")
        return

    all_rows.sort(key=lambda r: (r["time"], r["point_id"]))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"wrote {OUTPUT} — {len(all_rows)} rows")


if __name__ == "__main__":
    main()