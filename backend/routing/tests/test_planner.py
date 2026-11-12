"""End-to-end planner test with the routing and weather providers mocked."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from routing import geo, planner


def straight_route(lat0, lng0, lat1, lng1, n=200, speed_mph=50, wiggle=0.0):
    path = []
    for i in range(n + 1):
        t = i / n
        bump = wiggle * (1 - abs(2 * t - 1))
        path.append((lat0 + (lat1 - lat0) * t + bump, lng0 + (lng1 - lng0) * t))
    miles = geo.cumulative_miles(path)[-1]
    return {"path": path, "distance_mi": miles, "duration_s": miles / speed_mph * 3600,
            "segment_durations": None}


def fake_weather(windy_lat_band=None, wind=10.0):
    """Windy only for points whose latitude is within windy_lat_band."""

    def fetch(points, start, end):
        hours = int((end - start).total_seconds() // 3600) + 2
        out = {}
        for p in points:
            w = wind if windy_lat_band and windy_lat_band[0] <= p[0] <= windy_lat_band[1] else 5.0
            out[p] = {"base": start, "wind": [w] * hours, "gust": [w + 5] * hours,
                      "rain": [0.0] * hours, "snow": [0.0] * hours}
        return out

    return fetch


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.dep = datetime(2026, 11, 13, 8, 30, tzinfo=timezone.utc)
        self.fast = straight_route(35.0, -100.0, 35.0, -98.0)  # ~113 mi at lat 35
        self.slow = straight_route(35.0, -100.0, 35.0, -98.0, wiggle=0.5, speed_mph=45)

    def run_plan(self, weather, load=35_000, interval=None):
        with mock.patch("routing.planner.providers.get_routes",
                        return_value=[dict(self.fast), dict(self.slow)]), \
             mock.patch("routing.planner.providers.fetch_weather", side_effect=weather):
            return planner.plan((35.0, -100.0), (35.0, -98.0), self.dep, load, interval)

    def test_checkpoints_eta_and_shape(self):
        res = self.run_plan(fake_weather(), interval=25)
        route = next(r for r in res["routes"] if "Fastest" in r["tags"])
        miles = [c["mile"] for c in route["checkpoints"]]
        self.assertEqual(miles[0], 0)
        self.assertAlmostEqual(miles[-1], route["distance_mi"], delta=0.2)
        self.assertTrue(all(b - a <= 25.01 for a, b in zip(miles, miles[1:])))
        etas = [c["eta"] for c in route["checkpoints"]]
        self.assertEqual(etas, sorted(etas))
        self.assertEqual(route["checkpoints"][0]["eta"], "2026-11-13T08:30:00Z")
        self.assertEqual(len(route["checkpoints"][0]["forecast"]["level"]), 49)

    def test_auto_interval(self):
        self.assertEqual(planner.auto_interval(100), 10)
        self.assertEqual(planner.auto_interval(300), 25)
        self.assertEqual(planner.auto_interval(900), 50)

    def test_recommends_calmer_route_over_faster(self):
        # Fast route runs along lat 35.0; slow route bulges north (35.0..35.5).
        # Make the strip lat<=35.05 windy -> fast route is in 50 mph wind.
        res = self.run_plan(fake_weather((34.9, 35.05), wind=50.0), load=45_000)
        rec_id = res["recommendation"]["route_id"]
        best = res["routes"][0]
        self.assertEqual(best["id"], rec_id)
        self.assertTrue(best["recommended"])
        fastest = next(r for r in res["routes"] if "Fastest" in r["tags"])
        self.assertNotEqual(fastest["id"], rec_id)
        self.assertEqual(fastest["summary"]["no_travel_miles"] > 0, True)  # 50mph + 45k lb
        self.assertEqual(best["summary"]["no_travel_miles"] < fastest["summary"]["no_travel_miles"], True)

    def test_light_load_same_wind_is_only_severe(self):
        res = self.run_plan(fake_weather((34.9, 35.05), wind=50.0), load=10_000)
        fastest = next(r for r in res["routes"] if "Fastest" in r["tags"])
        self.assertEqual(fastest["summary"]["no_travel_miles"], 0)
        self.assertGreater(fastest["summary"]["severe_miles"], 0)

    def test_weather_window_covers_arrival_and_48h(self):
        seen = {}

        def capture(points, start, end):
            seen["start"], seen["end"] = start, end
            return fake_weather()(points, start, end)

        self.run_plan(capture)
        self.assertEqual(seen["start"], self.dep.replace(minute=0))
        self.assertGreaterEqual(seen["end"] - seen["start"], timedelta(hours=49))


if __name__ == "__main__":
    unittest.main()
