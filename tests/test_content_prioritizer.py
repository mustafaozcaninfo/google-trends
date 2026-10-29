import unittest

from content_prioritizer import prioritize_queries
from site_intelligence import build_gsc_index


class ContentPrioritizerTests(unittest.TestCase):
    def test_demote_puzzle(self):
        gsc = build_gsc_index([{
            "query": "nyt strands hints",
            "clicks": 0,
            "impressions": 5000,
            "ctr": 0,
            "position": 8,
        }])
        skip, new = prioritize_queries(["nyt strands hints"], gsc_index=gsc, published_slugs=set())
        self.assertEqual(len(skip), 1)
        self.assertEqual(len(new), 0)

    def test_new_thanksgiving_gap(self):
        gsc = build_gsc_index([{
            "query": "thanksgiving 2026",
            "clicks": 10,
            "impressions": 55000,
            "ctr": 0.02,
            "position": 4.2,
        }])
        skip, new = prioritize_queries(["thanksgiving 2026"], gsc_index=gsc, published_slugs=set())
        self.assertEqual(len(skip), 0)
        self.assertEqual(len(new), 1)
        self.assertIn("GSC", new[0].reason)


if __name__ == "__main__":
    unittest.main()
