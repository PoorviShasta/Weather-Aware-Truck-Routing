"""Third-party API clients. All free / no API key required:

* Geocoding autocomplete : Photon (OpenStreetMap)   https://photon.komoot.io
* Routing + alternatives : OSRM public demo server   https://router.project-osrm.org
* Weather (hourly)       : Open-Meteo                https://open-meteo.com

Override OSRM_BASE_URL to point at your own OSRM / compatible server.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

from . import geo

OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
PHOTON_URL = os.environ.get("PHOTON_URL", "https://photon.komoot.io/api/")
OPEN_METEO_URL = os.environ.get(
    "OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast"
)
# OSRM's public profile is "car". Trucks are slower (speed limiters, grades,
# ramps) so we stretch durations by a configurable factor.
TRUCK_SPEED_FACTOR = float(os.environ.get("TRUCK_SPEED_FACTOR", "1.12"))

_session = requests.Session()
_session.headers["User-Agent"] = "weather-truck-routing/1.0 (assessment project)"


class UpstreamError(Exception):
    """A third-party API failed or returned nothing usable."""


def _get_json(url, params=None, timeout=25, retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            resp = _session.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last = str(exc)
        else:
            if resp.status_code < 300:
                return resp.json()
            try:
                body = resp.json()
                last = body.get("message") or body.get("reason") or body.get("code")
            except ValueError:
                last = None
            last = last or f"HTTP {resp.status_code}"
            if resp.status_code not in (429, 500, 502, 503, 504):
                break  # not worth retrying
        if attempt < retries:
            time.sleep(0.8 * (attempt + 1))
    raise UpstreamError(f"{url.split('/')[2]}: {last}")


# --------------------------------------------------------------------------
# Geocoding
# --------------------------------------------------------------------------
def geocode(query, limit=5):
    data = _get_json(PHOTON_URL, {"q": query, "limit": limit, "lang": "en"})
    results = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        lon, lat = f["geometry"]["coordinates"]
        parts = [p.get("name"), p.get("street"), p.get("city"), p.get("state"), p.get("country")]
        label = ", ".join(dict.fromkeys(x for x in parts if x))
        results.append({"label": label, "lat": lat, "lng": lon})
    return results


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------
def _osrm(points, alternatives):
    coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in points)
    url = f"{OSRM_BASE_URL}/route/v1/driving/{coords}"
    data = _get_json(
        url,
        {
            "alternatives": "3" if alternatives else "false",
            "overview": "full",
            "geometries": "geojson",
            "annotations": "duration",
            "steps": "false",
        },
    )
    if data.get("code") != "Ok" or not data.get("routes"):
        raise UpstreamError("No drivable route found between those locations.")
    out = []
    for r in data["routes"]:
        path = [(lat, lng) for lng, lat in r["geometry"]["coordinates"]]
        durs = []
        for leg in r.get("legs", []):
            durs.extend(leg.get("annotation", {}).get("duration", []))
        out.append(
            {
                "path": path,
                "distance_mi": r["distance"] / 1609.344,
                "duration_s": r["duration"] * TRUCK_SPEED_FACTOR,
                # per-segment durations let us compute accurate ETAs; fall back
                # to proportional-by-distance when they do not line up.
                "segment_durations": (
                    [d * TRUCK_SPEED_FACTOR for d in durs]
                    if len(durs) == len(path) - 1
                    else None
                ),
            }
        )
    return out


def get_routes(origin, destination, want=3):
    """Up to `want` distinct driving routes.

    OSRM's `alternatives` often returns only 1-2 routes, so we top up by routing
    through detour waypoints placed beside the main route.
    """
    routes = _osrm([origin, destination], alternatives=True)
    routes = _dedupe(routes)[:want]

    if len(routes) < want:
        main = routes[0]
        cum = geo.cumulative_miles(main["path"])
        total = cum[-1]
        if total > 3:
            detour = max(6.0, 0.12 * total)
            candidates = [(0.5, 1), (0.5, -1), (0.35, 1), (0.65, -1), (0.35, -1), (0.65, 1)]
            attempts = 0
            for frac, side in candidates:
                if len(routes) >= want or attempts >= 4:
                    break
                attempts += 1
                via = geo.offset_point(main["path"], cum, frac, detour, side)
                try:
                    extra = _osrm([origin, via, destination], alternatives=False)[0]
                except UpstreamError:
                    continue
                if extra["distance_mi"] > main["distance_mi"] * 1.6 + 20:
                    continue  # absurd detour
                if not any(geo.is_similar(extra["path"], r["path"]) for r in routes):
                    routes.append(extra)
    return routes[:want]


def _dedupe(routes):
    kept = []
    for r in routes:
        if not any(geo.is_similar(r["path"], k["path"]) for k in kept):
            kept.append(r)
    return kept


# --------------------------------------------------------------------------
# Weather
# --------------------------------------------------------------------------
_HOURLY = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
_CACHE_TTL = 900  # seconds
_cache = {}
_cache_lock = threading.Lock()
_BATCH = 40


def _parse_location(loc):
    h = loc["hourly"]
    base = datetime.strptime(h["time"][0], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)

    def col(name):
        return [v if v is not None else 0.0 for v in h.get(name, [])]

    rain = [a + b for a, b in zip(col("rain"), col("showers"))]
    return {
        "base": base,
        "wind": col("wind_speed_10m"),
        "gust": col("wind_gusts_10m"),
        "rain": rain,
        "snow": col("snowfall"),
    }


def _fetch_batch(points, start_date, end_date):
    data = _get_json(
        OPEN_METEO_URL,
        {
            "latitude": ",".join(f"{p[0]:.4f}" for p in points),
            "longitude": ",".join(f"{p[1]:.4f}" for p in points),
            "hourly": _HOURLY,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "UTC",
            "start_date": start_date,
            "end_date": end_date,
        },
        timeout=40,
    )
    locations = data if isinstance(data, list) else [data]
    if len(locations) != len(points):
        raise UpstreamError("Open-Meteo returned an unexpected number of locations.")
    return [_parse_location(loc) for loc in locations]


def fetch_weather(points, start, end):
    """Hourly weather series for each (lat, lng) between two UTC datetimes.

    Returns {point: {"base": datetime, "wind": [...], "gust": [...],
    "rain": [...], "snow": [...]}}. Index i is `base + i hours`.
    """
    start_date, end_date = start.date().isoformat(), end.date().isoformat()
    result, missing, now = {}, [], time.time()
    with _cache_lock:
        for p in dict.fromkeys(points):
            hit = _cache.get((p, start_date, end_date))
            if hit and now - hit[0] < _CACHE_TTL:
                result[p] = hit[1]
            else:
                missing.append(p)

    batches = [missing[i : i + _BATCH] for i in range(0, len(missing), _BATCH)]
    if batches:
        with ThreadPoolExecutor(max_workers=4) as pool:
            fetched = list(pool.map(lambda b: _fetch_batch(b, start_date, end_date), batches))
        with _cache_lock:
            for batch, series_list in zip(batches, fetched):
                for p, series in zip(batch, series_list):
                    result[p] = series
                    _cache[(p, start_date, end_date)] = (now, series)
    return result
