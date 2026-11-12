"""Weather risk classification and route ranking.

Pure functions only (no I/O) so the rules are easy to read and unit-test.

Boundary convention (the brief's table has overlapping edges such as "0.10-0.25"
and "0.25-0.50"): the *lower* edge of Low->Moderate is inclusive, every other
edge is "greater than" the stated upper bound, which matches the table's
">1.00" / ">3.0" wording for No Travel. Wind uses whole-mph bands, so
34.9 mph is Moderate and 35.0 mph is High.
"""

LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL = range(5)
LEVEL_NAMES = ["Low", "Moderate", "High", "Severe", "No Travel"]

# (threshold, inclusive). Level = number of thresholds the value passes.
WIND_STEPS = [(25, True), (35, True), (45, True), (55, True)]  # mph
RAIN_STEPS = [(0.10, True), (0.25, False), (0.50, False), (1.00, False)]  # in/hr
SNOW_STEPS = [(0.5, True), (1.0, False), (2.0, False), (3.0, False)]  # in/hr

HEAVY_LOAD_NO_TRAVEL_LB = 30_000  # with 45-54 mph wind
HEAVY_LOAD_SEVERE_LB = 40_000  # with 35-44 mph wind


def _level(value, steps):
    level = 0
    for threshold, inclusive in steps:
        if value > threshold or (inclusive and value >= threshold):
            level += 1
        else:
            break
    return level


def wind_level(wind_mph, load_lb):
    """Wind level including the load-based escalation rules."""
    level = _level(wind_mph, WIND_STEPS)
    if wind_mph >= 55:
        return NO_TRAVEL  # any load
    if wind_mph >= 45 and load_lb > HEAVY_LOAD_NO_TRAVEL_LB:
        return NO_TRAVEL
    if wind_mph >= 35 and load_lb > HEAVY_LOAD_SEVERE_LB:
        return max(level, SEVERE)
    return level


def rain_level(rain_in_hr):
    return _level(rain_in_hr, RAIN_STEPS)


def snow_level(snow_in_hr):
    return _level(snow_in_hr, SNOW_STEPS)


def assess(wind_mph, rain_in_hr, snow_in_hr, load_lb):
    """Overall level = worst of the three hazards. Returns (level, per-hazard dict)."""
    factors = {
        "wind": wind_level(wind_mph, load_lb),
        "rain": rain_level(rain_in_hr),
        "snow": snow_level(snow_in_hr),
    }
    return max(factors.values()), factors


def segment_miles(miles, total):
    """Miles of road each checkpoint 'represents' (halfway to its neighbours)."""
    n = len(miles)
    if n == 0:
        return []
    bounds = [0.0] + [(miles[i - 1] + miles[i]) / 2 for i in range(1, n)] + [total]
    return [max(bounds[i + 1] - bounds[i], 0.0) for i in range(n)]


def summarize(levels, weights):
    """Miles per level, mileage-weighted average level and worst level."""
    miles = [0.0] * 5
    for lvl, w in zip(levels, weights):
        miles[lvl] += w
    total = sum(weights) or 1.0
    avg = sum(i * m for i, m in enumerate(miles)) / total
    worst = max(levels) if levels else LOW
    return {
        "low_miles": round(miles[LOW], 1),
        "moderate_miles": round(miles[MODERATE], 1),
        "high_miles": round(miles[HIGH], 1),
        "severe_miles": round(miles[SEVERE], 1),
        "no_travel_miles": round(miles[NO_TRAVEL], 1),
        "avg_risk": round(avg, 3),  # 0 (Low) .. 4 (No Travel)
        "max_level": worst,
        "max_level_name": LEVEL_NAMES[worst],
    }


# Ordered criteria. "No Travel" miles come first: a stretch you may not drive at
# all is strictly worse than a Severe one. Then the brief's order:
# Severe miles -> High miles -> average risk -> travel time.
CRITERIA = [
    ("no_travel_miles", "No Travel miles", "mi"),
    ("severe_miles", "Severe miles", "mi"),
    ("high_miles", "High-risk miles", "mi"),
    ("avg_risk", "average risk", ""),
    ("duration_min", "travel time", "min"),
]


def sort_key(route):
    s = route["summary"]
    return (
        round(s["no_travel_miles"], 1),
        round(s["severe_miles"], 1),
        round(s["high_miles"], 1),
        round(s["avg_risk"], 2),
        route["duration_min"],
    )


def _value(route, field):
    if field == "duration_min":
        return route["duration_min"]
    return route["summary"][field]


def _fmt(value, unit):
    if unit == "mi":
        return f"{value:.0f} mi"
    if unit == "min":
        h, m = divmod(int(round(value)), 60)
        return f"{h}h {m:02d}m"
    return f"{value:.2f}"


def rank_routes(routes):
    """Sort best-first, annotate rank/recommended, return recommendation dict."""
    ordered = sorted(routes, key=sort_key)
    for i, r in enumerate(ordered):
        r["rank"] = i + 1
        r["recommended"] = i == 0
    best = ordered[0]

    reason = "Only one route available."
    if len(ordered) > 1:
        runner = ordered[1]
        kb, kr = sort_key(best), sort_key(runner)
        reason = (
            f"{best['name']} is equal to {runner['name']} on every criterion."
        )
        for i, (field, label, unit) in enumerate(CRITERIA):
            if kb[i] != kr[i]:
                reason = (
                    f"{best['name']} has lower {label} "
                    f"({_fmt(_value(best, field), unit)} vs "
                    f"{_fmt(_value(runner, field), unit)} for {runner['name']})."
                )
                break

    warnings = []
    bs = best["summary"]
    if bs["no_travel_miles"] > 0:
        warnings.append(
            "Every route crosses No Travel conditions at your chosen departure "
            "time. Consider delaying departure or reducing load."
        )
    elif bs["severe_miles"] > 0:
        warnings.append(
            f"Even the best route has {bs['severe_miles']:.0f} mi of Severe "
            "weather. Consider a different departure time."
        )
    return {"route_id": best["id"], "reason": reason, "warnings": warnings}
