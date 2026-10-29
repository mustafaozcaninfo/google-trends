import unittest

from editor_pick import calendar_fit_score, rank_trend_picks
from signals import score_opportunity, trending_match_points
from trending_service import build_trend_index, lookup_trend, normalize_csv_rows, sort_by_volume


class TrendingServiceTests(unittest.TestCase):
    def test_parse_csv_volume(self):
        rows = normalize_csv_rows([
            {"Trends": "thanksgiving 2026", "Search volume": "50K+", "Trend breakdown": "a,b"},
        ])
        self.assertEqual(rows[0]["volume_min"], 50_000)
        self.assertEqual(rows[0]["related_queries"], ["a", "b"])

    def test_index_merges_rss_and_full(self):
        idx = build_trend_index(
            [{"keyword": "crime", "volume_min": 1000, "volume_text": "1000+", "related_queries": []}],
            [{"keyword": "crime", "volume_min": 500_000, "volume_text": "500K+", "related_queries": ["x"]}],
        )
        self.assertTrue(idx["crime"]["in_rss"])
        self.assertTrue(idx["crime"]["in_full"])
        self.assertEqual(idx["crime"]["volume_min"], 500_000)

    def test_lookup_substring(self):
        idx = build_trend_index([], [{"keyword": "election day 2026 texas", "volume_min": 10_000, "volume_text": "10K+"}])
        hit = lookup_trend("election day 2026 texas counties", idx)
        self.assertIsNotNone(hit)

    def test_volume_scoring(self):
        pts, parts = trending_match_points({"in_rss": True, "in_full": True, "volume_min": 100_000})
        self.assertGreaterEqual(pts, 40)
        self.assertGreater(parts["trending_volume"], 0)

    def test_score_uses_full_volume(self):
        idx = build_trend_index([], [{"keyword": "medicare open enrollment 2026", "volume_min": 80_000, "volume_text": "80K+"}])
        row = score_opportunity(
            "medicare open enrollment 2026 deadline",
            relevance=400,
            related_index={},
            trending_keys=set(),
            trend_index=idx,
            interest=None,
            published_slugs=set(),
        )
        self.assertTrue(row["trends_trending_now"])
        self.assertGreater(row["score_breakdown"]["trending_volume"], 0)

    def test_calendar_fit(self):
        self.assertGreater(calendar_fit_score("thanksgiving 2026 school break"), 40)
        self.assertLess(calendar_fit_score("cavaliers vs 76ers"), 15)

    def test_rank_picks(self):
        trends = sort_by_volume([
            {"keyword": "thanksgiving 2026", "volume_min": 50_000, "volume_text": "50K+"},
            {"keyword": "nba finals", "volume_min": 500_000, "volume_text": "500K+"},
        ])
        picks = rank_trend_picks(trends, limit=2, min_fit=10)
        self.assertTrue(any("thanksgiving" in p["keyword"] for p in picks))


if __name__ == "__main__":
    unittest.main()
