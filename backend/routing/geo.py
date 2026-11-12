"""Small geometry helpers (no third-party deps)."""
import bisect
import math

EARTH_RADIUS_MI = 3958.7613


def haversine_mi(a, b):
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def cumulative_miles(path):
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + haversine_mi(path[i - 1], path[i]))
    return cum


def interp(xs, ys, x):
    """Linear interpolation of ys over ascending xs (clamped at the ends)."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_right(xs, x)
    x0, x1 = xs[i - 1], xs[i]
    if x1 == x0:
        return ys[i]
    t = (x - x0) / (x1 - x0)
    return ys[i - 1] + t * (ys[i] - ys[i - 1])


def point_at(path, cum, miles):
    """(lat, lng) at a distance along the polyline."""
    return (
        interp(cum, [p[0] for p in path], miles),
        interp(cum, [p[1] for p in path], miles),
    )


def downsample(path, max_points=1500):
    if len(path) <= max_points:
        return list(path)
    step = len(path) / max_points
    out = [path[int(i * step)] for i in range(max_points)]
    out.append(path[-1])
    return out


def is_similar(path_a, path_b, tol_mi=2.0, samples=25):
    """True when path_a stays within tol_mi of path_b everywhere (duplicate route)."""
    b = downsample(path_b, 400)
    for i in range(samples):
        p = path_a[int(i * (len(path_a) - 1) / (samples - 1))]
        if min(haversine_mi(p, q) for q in b) > tol_mi:
            return False
    return True


def offset_point(path, cum, fraction, distance_mi, side=1):
    """Point `distance_mi` to the side of the route at `fraction` of its length."""
    total = cum[-1]
    d = total * fraction
    p0 = point_at(path, cum, max(d - 0.02 * total, 0))
    p1 = point_at(path, cum, min(d + 0.02 * total, total))
    mid = point_at(path, cum, d)
    lat_mi = 69.0
    lon_mi = 69.0 * max(math.cos(math.radians(mid[0])), 0.01)
    dy = (p1[0] - p0[0]) * lat_mi
    dx = (p1[1] - p0[1]) * lon_mi
    norm = math.hypot(dx, dy) or 1.0
    px, py = -dy / norm * side, dx / norm * side  # perpendicular
    return (mid[0] + py * distance_mi / lat_mi, mid[1] + px * distance_mi / lon_mi)
