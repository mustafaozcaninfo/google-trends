import unittest

from signals import opportunity_tier


class OpportunityTierTests(unittest.TestCase):
    def test_high_volume_is_catch_now(self):
        tier = opportunity_tier(
            score=40,
            rising=False,
            on_trending=False,
            published=False,
            interest=None,
            trends_volume_min=80_000,
        )
        self.assertEqual(tier, "Catch now")


if __name__ == "__main__":
    unittest.main()
