import unittest

from published_slugs import match_published, query_to_slug
from signals import fuzzy_trending_key_match, rank_autocomplete_rows, score_opportunity


class SignalsTests(unittest.TestCase):
    def test_query_to_slug(self):
        self.assertIn("thanksgiving", query_to_slug("Thanksgiving 2026 NFL"))

    def test_published_penalty(self):
        slugs = {"thanksgiving-2026-nfl-games"}
        row = score_opportunity(
            "thanksgiving 2026 nfl games",
            relevance=600,
            related_index={},
            trending_keys=set(),
            interest=None,
            published_slugs=slugs,
        )
        self.assertTrue(row["published_slug"])
        self.assertLess(row["score"], 30)

    def test_rising_boost(self):
        rel = {"thanksgiving 2026 nfl": {"rising": True, "top": False, "seeds": {"x"}, "values": []}}
        row = score_opportunity(
            "thanksgiving 2026 nfl",
            relevance=500,
            related_index=rel,
            trending_keys=set(),
            interest=None,
            published_slugs=set(),
        )
        self.assertGreater(row["score"], 50)
        self.assertEqual(row["tier"], "Catch now")

    def test_lookup_related_fuzzy(self):
        from signals import lookup_related, index_rising
        obs = [{
            "seed": "election",
            "data": {
                "top": [{"query": "election day 2026 texas sample", "value": 100}],
                "rising": [],
            },
        }]
        idx = index_rising(obs)
        hit = lookup_related("election day 2026 texas county", idx)
        self.assertTrue(hit.get("top"))

    def test_score_breakdown_present(self):
        row = score_opportunity(
            "sample ballot 2026 tarrant county",
            relevance=550,
            discover_source="a:t",
            related_index={},
            trending_keys=set(),
            interest=None,
            published_slugs=set(),
        )
        self.assertIn("score_breakdown", row)
        self.assertGreater(row["score_breakdown"]["autocomplete"], 0)

    def test_fuzzy_trending_requires_tokens(self):
        keys = {"black friday deals 2026"}
        self.assertFalse(fuzzy_trending_key_match("local news today", keys))
        self.assertTrue(fuzzy_trending_key_match("black friday deals near me", keys))

    def test_rank_sorts_by_score(self):
        ac = [{"query": "low", "relevance": 100, "depth": 1}, {"query": "high", "relevance": 600, "depth": 1}]
        ranked = rank_autocomplete_rows(ac, related_observations=[], trending_list=[], interest_by_query={}, published_slugs=set())
        self.assertEqual(ranked[0]["query"], "high")


if __name__ == "__main__":
    unittest.main()
