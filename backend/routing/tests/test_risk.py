import unittest

from routing import risk
from routing.risk import HIGH, LOW, MODERATE, NO_TRAVEL, SEVERE


class WindTests(unittest.TestCase):
    def test_bands_light_load(self):
        cases = {10: LOW, 24.9: LOW, 25: MODERATE, 34.9: MODERATE, 35: HIGH,
                 44.9: HIGH, 45: SEVERE, 54.9: SEVERE, 55: NO_TRAVEL, 80: NO_TRAVEL}
        for wind, expected in cases.items():
            self.assertEqual(risk.wind_level(wind, 10_000), expected, wind)

    def test_55_is_no_travel_for_any_load(self):
        self.assertEqual(risk.wind_level(55, 0), NO_TRAVEL)

    def test_45_54_over_30k_is_no_travel(self):
        self.assertEqual(risk.wind_level(45, 30_001), NO_TRAVEL)
        self.assertEqual(risk.wind_level(54, 45_000), NO_TRAVEL)
        self.assertEqual(risk.wind_level(50, 30_000), SEVERE)  # not > 30,000

    def test_35_44_over_40k_is_severe(self):
        self.assertEqual(risk.wind_level(35, 40_001), SEVERE)
        self.assertEqual(risk.wind_level(44, 40_000), HIGH)  # not > 40,000
        self.assertEqual(risk.wind_level(30, 79_000), MODERATE)  # rule needs >=35


class RainSnowTests(unittest.TestCase):
    def test_rain(self):
        cases = {0.09: LOW, 0.10: MODERATE, 0.25: MODERATE, 0.26: HIGH,
                 0.50: HIGH, 0.51: SEVERE, 1.00: SEVERE, 1.01: NO_TRAVEL}
        for v, expected in cases.items():
            self.assertEqual(risk.rain_level(v), expected, v)

    def test_snow(self):
        cases = {0.4: LOW, 0.5: MODERATE, 1.0: MODERATE, 1.1: HIGH,
                 2.0: HIGH, 2.1: SEVERE, 3.0: SEVERE, 3.1: NO_TRAVEL}
        for v, expected in cases.items():
            self.assertEqual(risk.snow_level(v), expected, v)

    def test_assess_takes_worst(self):
        level, factors = risk.assess(20, 0.3, 2.5, 10_000)
        self.assertEqual(level, SEVERE)
        self.assertEqual(factors, {"wind": LOW, "rain": HIGH, "snow": SEVERE})


class SummaryAndRankingTests(unittest.TestCase):
    def test_segment_miles_sum_to_total(self):
        miles = [0, 25, 50, 75, 90]
        self.assertAlmostEqual(sum(risk.segment_miles(miles, 90)), 90)

    def test_summarize(self):
        s = risk.summarize([LOW, SEVERE, HIGH], [10, 10, 10])
        self.assertEqual(s["severe_miles"], 10)
        self.assertEqual(s["high_miles"], 10)
        self.assertAlmostEqual(s["avg_risk"], (0 + 3 + 2) / 3, places=3)
        self.assertEqual(s["max_level_name"], "Severe")

    @staticmethod
    def _route(rid, severe, high, avg, minutes, nt=0.0):
        return {"id": rid, "name": rid, "duration_min": minutes,
                "summary": {"no_travel_miles": nt, "severe_miles": severe,
                            "high_miles": high, "avg_risk": avg}}

    def test_severe_miles_beat_everything(self):
        a = self._route("A", severe=0, high=100, avg=2.0, minutes=900)
        b = self._route("B", severe=25, high=0, avg=0.1, minutes=100)
        rec = risk.rank_routes([b, a])
        self.assertEqual(rec["route_id"], "A")
        self.assertIn("Severe", rec["reason"])

    def test_high_then_avg_then_time(self):
        a = self._route("A", 0, 50, 1.0, 100)
        b = self._route("B", 0, 25, 1.5, 300)
        self.assertEqual(risk.rank_routes([a, b])["route_id"], "B")
        c = self._route("C", 0, 25, 1.2, 500)
        self.assertEqual(risk.rank_routes([b, c])["route_id"], "C")
        d = self._route("D", 0, 25, 1.2, 200)
        self.assertEqual(risk.rank_routes([c, d])["route_id"], "D")

    def test_no_travel_is_ranked_last_and_warns(self):
        a = self._route("A", 0, 0, 0.5, 100, nt=12.5)
        b = self._route("B", 50, 0, 1.0, 100)
        rec = risk.rank_routes([a, b])
        self.assertEqual(rec["route_id"], "B")
        c = self._route("C", 0, 0, 0.5, 90, nt=25)
        rec = risk.rank_routes([a, c])
        self.assertTrue(rec["warnings"])


if __name__ == "__main__":
    unittest.main()
