import unittest
from datetime import date

from future_demand import future_demand_score


class FutureDemandTests(unittest.TestCase):
    def test_thanksgiving_countdown(self):
        fd, _ = future_demand_score("how many days until thanksgiving 2026", today=date(2026, 10, 23))
        self.assertGreaterEqual(fd, 55)

    def test_past_box_score_low(self):
        fd, reasons = future_demand_score("bears patriots box score", today=date(2026, 10, 23))
        self.assertLess(fd, 40)
        self.assertTrue(any("gürültü" in r for r in reasons))

    def test_far_year_penalty(self):
        fd, _ = future_demand_score("what day is thanksgiving 2030", today=date(2026, 10, 23))
        fd26, _ = future_demand_score("thanksgiving 2026 date", today=date(2026, 10, 23))
        self.assertGreater(fd26, fd)


if __name__ == "__main__":
    unittest.main()
