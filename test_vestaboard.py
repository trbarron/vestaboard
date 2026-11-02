"""Unit tests for vestaboard helpers.

Run with: python -m unittest test_vestaboard
"""
import sys
import types
import unittest
from datetime import datetime

# Stub out config so vestaboard can be imported without a real config.py
_fake_config = types.ModuleType("config")
_fake_config.VESTABOARD_API_KEY = "test"
_fake_config.WEATHER_API_KEY = "test"
_fake_config.WEATHER_LAT = 0.0
_fake_config.WEATHER_LON = 0.0
_fake_config.COUNTER_START_DATE = "2025-01-01"
_fake_config.COUNTER_LABEL = "Test"
_fake_config.COUNTER_USE_MONTHS = True
sys.modules.setdefault("config", _fake_config)

import vestaboard  # noqa: E402


class TestParseTimeToSeconds(unittest.TestCase):
    def test_hms(self):
        self.assertEqual(vestaboard.parse_time_to_seconds("1:22:25"), 4945)

    def test_ms(self):
        self.assertEqual(vestaboard.parse_time_to_seconds("20:00"), 1200)

    def test_zero(self):
        self.assertEqual(vestaboard.parse_time_to_seconds("0:00:00"), 0)

    def test_malformed(self):
        self.assertEqual(vestaboard.parse_time_to_seconds("--"), 0)
        self.assertEqual(vestaboard.parse_time_to_seconds(""), 0)
        self.assertEqual(vestaboard.parse_time_to_seconds(None), 0)


class TestWorkTimeLabel(unittest.TestCase):
    def test_dominant_checo(self):
        # 1:22:25 total, all Checo -> Checo
        total = vestaboard.parse_time_to_seconds("1:22:25")
        self.assertEqual(vestaboard.get_work_time_label(total, 0, total), "Checo")

    def test_dominant_tuni(self):
        self.assertEqual(vestaboard.get_work_time_label(3600, 3000, 600), "Tuni")

    def test_under_threshold(self):
        # 20 min all Checo -> still "Cats" (under 30 min)
        total = vestaboard.parse_time_to_seconds("0:20:00")
        self.assertEqual(vestaboard.get_work_time_label(total, 0, total), "Cats")

    def test_split_over_threshold(self):
        # Over 30 min but 50/50 -> "Cats"
        self.assertEqual(vestaboard.get_work_time_label(3600, 1800, 1800), "Cats")

    def test_zero(self):
        self.assertEqual(vestaboard.get_work_time_label(0, 0, 0), "Cats")

    def test_exactly_80_percent(self):
        # 80% share at the boundary should credit the cat
        self.assertEqual(vestaboard.get_work_time_label(3600, 2880, 720), "Tuni")


class TestDaysSince(unittest.TestCase):
    def test_before_start_returns_zero(self):
        future = datetime.now().strftime("%Y-%m-%d").replace(
            datetime.now().strftime("%Y"), str(datetime.now().year + 1)
        )
        self.assertEqual(vestaboard.days_since(future, use_months=True), "0m 0d")

    def test_weeks_format(self):
        # A fixed past date in weeks format should be "Nw Md"
        result = vestaboard.days_since("2025-01-01", use_months=False)
        self.assertRegex(result, r"^\d+w \d+d$")

    def test_months_format(self):
        result = vestaboard.days_since("2025-01-01", use_months=True)
        self.assertRegex(result, r"^-?\d+m -?\d+d$")

    def test_invalid_format(self):
        self.assertEqual(vestaboard.days_since("not-a-date", use_months=True), "0m 0d")
        self.assertEqual(vestaboard.days_since("not-a-date", use_months=False), "0w 0d")


if __name__ == "__main__":
    unittest.main()
