"""Orchestrates: routes -> checkpoints -> ETAs -> weather -> risk -> recommendation."""
from datetime import timedelta

from . import geo, providers, risk

HEAT_HOURS = 48  # forecast slider covers departure + 0..48 h
ROUTE_NAMES = ["Route A", "Route B", "Route C"]


def auto_interval(total_miles):
    if total_miles <= 150:
        return 10
    if total_miles <= 500:
        return 25
    return 50


def checkpoint_miles(total, interval):
    """0, I, 2I ... and always the destination (merged if it is very close)."""
    miles = [i * interval for i in range(int(total // interval) + 1)]
    if total - miles[-1] < 0.25 * interval and len(miles) > 1:
        miles[-1] = total
    elif total - miles[-1] > 1e-6:
        miles.append(total)
    return [round(m, 3) for m in miles]


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_geometry(raw, departure, interval):
    """Checkpoints (position, mile, ETA) for one raw route."""
    path = raw["path"]
    cum = geo.cumulative_miles(path)
    scale = raw["distance_mi"] / cum[-1] if cum[-1] else 1.0
    cum = [c * scale for c in cum]
    total = cum[-1]

    if raw.get("segment_durations"):
        tcum = [0.0]
        for d in raw["segment_durations"]:
            tcum.append(tcum[-1] + d)
        k = raw["duration_s"] / tcum[-1] if tcum[-1] else 1.0
        tcum = [t * k for t in tcum]
    else:  # constant average speed
        tcum = [c / total * raw["duration_s"] for c in cum] if total else [0.0] * len(cum)

    use_interval = interval or auto_interval(total)
    checkpoints = []
    for mile in checkpoint_miles(total, use_interval):
        lat, lng = geo.point_at(path, cum, mile)
        eta_s = geo.interp(cum, tcum, mile)
        checkpoints.append(
            {
                "mile": round(mile, 1),
                "lat": round(lat, 5),
                "lng": round(lng, 5),
                "eta_s": eta_s,
                "eta_dt": departure + timedelta(seconds=eta_s),
            }
        )
    return {
        "path": path,
        "total_mi": total,
        "duration_s": raw["duration_s"],
        "checkpoints": checkpoints,
        "interval": use_interval,
    }


def _idx(series, when):
    i = int(round((when - series["base"]).total_seconds() / 3600))
    return min(max(i, 0), len(series["wind"]) - 1)


def plan(origin, destination, departure, load_lb, interval=None):
    """origin/destination are (lat, lng); departure is an aware UTC datetime."""
    raw_routes = providers.get_routes(origin, destination)
    raw_routes.sort(key=lambda r: r["duration_s"])

    built = [_build_geometry(r, departure, interval) for r in raw_routes]

    # One weather request covers every checkpoint of every route, for the whole
    # window we need: the heatmap hours AND the longest trip's arrival times.
    dep_hour = departure.replace(minute=0, second=0, microsecond=0)
    last_eta = max(r["checkpoints"][-1]["eta_dt"] for r in built)
    end = max(dep_hour + timedelta(hours=HEAT_HOURS), last_eta) + timedelta(hours=1)
    points = [(c["lat"], c["lng"]) for r in built for c in r["checkpoints"]]
    weather = providers.fetch_weather(points, dep_hour, end)

    routes = []
    for n, b in enumerate(built):
        levels, cps = [], []
        for c in b["checkpoints"]:
            w = weather[(c["lat"], c["lng"])]
            i = _idx(w, c["eta_dt"])
            wind, gust, rain, snow = w["wind"][i], w["gust"][i], w["rain"][i], w["snow"][i]
            level, factors = risk.assess(wind, rain, snow, load_lb)
            levels.append(level)

            # Heatmap series: conditions at (departure + h) for h = 0..48.
            hours = {"level": [], "wind": [], "rain": [], "snow": []}
            for h in range(HEAT_HOURS + 1):
                j = _idx(w, dep_hour + timedelta(hours=h))
                lv, _ = risk.assess(w["wind"][j], w["rain"][j], w["snow"][j], load_lb)
                hours["level"].append(lv)
                hours["wind"].append(round(w["wind"][j], 1))
                hours["rain"].append(round(w["rain"][j], 3))
                hours["snow"].append(round(w["snow"][j], 2))

            cps.append(
                {
                    "mile": c["mile"],
                    "lat": c["lat"],
                    "lng": c["lng"],
                    "eta": _iso(c["eta_dt"]),
                    "wind_mph": round(wind, 1),
                    "gust_mph": round(gust, 1),
                    "rain_in_hr": round(rain, 3),
                    "snow_in_hr": round(snow, 2),
                    "level": level,
                    "level_name": risk.LEVEL_NAMES[level],
                    "factors": {k: risk.LEVEL_NAMES[v] for k, v in factors.items()},
                    "forecast": hours,
                }
            )

        weights = risk.segment_miles([c["mile"] for c in cps], b["total_mi"])
        summary = risk.summarize(levels, weights)
        worst = max(cps, key=lambda c: c["level"])
        summary["worst_mile"] = worst["mile"]
        arrival = b["checkpoints"][-1]["eta_dt"]

        routes.append(
            {
                "id": f"route-{n + 1}",
                "name": ROUTE_NAMES[n] if n < len(ROUTE_NAMES) else f"Route {n + 1}",
                "distance_mi": round(b["total_mi"], 1),
                "duration_min": round(b["duration_s"] / 60),
                "arrival": _iso(arrival),
                "interval_miles": b["interval"],
                "geometry": [[round(la, 5), round(ln, 5)] for la, ln in geo.downsample(b["path"])],
                "summary": summary,
                "checkpoints": cps,
            }
        )

    fastest = min(routes, key=lambda r: r["duration_min"])
    recommendation = risk.rank_routes(routes)
    for r in routes:
        r["tags"] = []
        if r is fastest:
            r["tags"].append("Fastest")
        if r["recommended"]:
            r["tags"].append("Recommended")

    return {
        "departure": _iso(departure),
        "load_lb": load_lb,
        "heat_hours": HEAT_HOURS,
        "heat_base": _iso(dep_hour),
        "routes": sorted(routes, key=lambda r: r["rank"]),
        "recommendation": recommendation,
    }
