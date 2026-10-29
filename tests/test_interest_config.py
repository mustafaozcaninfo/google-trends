import unittest

import pandas as pd

from interest_config import DEFAULT_INTEREST_TIMEFRAME, INTEREST_TIMEFRAME_IDS
from trends_layer import series_to_points


class InterestConfigTests(unittest.TestCase):
    def test_default_is_24h(self):
        self.assertEqual(DEFAULT_INTEREST_TIMEFRAME, "now 1-d")

    def test_order_fresh_before_7d(self):
        self.assertEqual(INTEREST_TIMEFRAME_IDS[0], "now 4-H")
        self.assertEqual(INTEREST_TIMEFRAME_IDS[-1], "now 7-d")

    def test_series_to_points(self):
        df = pd.DataFrame({"foo": [10.0, 30.0]}, index=pd.to_datetime(["2026-01-01", "2026-01-02"]))
        pts = series_to_points(df, "foo")
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[-1]["v"], 30.0)


if __name__ == "__main__":
    unittest.main()
