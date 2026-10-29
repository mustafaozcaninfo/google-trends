import tempfile
import unittest
from pathlib import Path

from site_intelligence import (
    apply_site_intelligence,
    build_gsc_index,
    fc_theme_boost,
    parse_gsc_queries_csv,
    top_gsc_gaps,
)


class SiteIntelligenceTests(unittest.TestCase):
    def test_theme_boost_ballot(self):
        pts, label, _ = fc_theme_boost("printable sample ballot by zip code 2026")
        self.assertGreaterEqual(pts, 35)
        self.assertIn("ballot", label)

    def test_theme_boost_thanksgiving(self):
        pts, label, _ = fc_theme_boost("thanksgiving 2026")
        self.assertGreaterEqual(pts, 40)
        self.assertEqual(label, "thanksgiving_hub")

    def test_gsc_apply_lifts_thanksgiving(self):
        gsc = build_gsc_index([{
            "query": "thanksgiving 2026",
            "clicks": 10,
            "impressions": 55000,
            "ctr": 0.02,
            "position": 4.2,
        }])
        rows = [{
            "query": "thanksgiving 2026",
            "score": 50,
            "tier": "Write soon",
            "score_breakdown": {},
            "signals": "",
        }]
        out = apply_site_intelligence(rows, gsc)
        self.assertGreater(out[0]["site_boost"], 30)
        self.assertEqual(out[0]["tier"], "Catch now")

    def test_parse_csv(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "q.csv"
        path.write_text(
            "Top queries,Clicks,Impressions,CTR,Position\n"
            "sample ballot,10,1000,1%,8.5\n",
            encoding="utf-8",
        )
        rows = parse_gsc_queries_csv(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["impressions"], 1000.0)

    def test_top_gsc_gaps_orders_high_imp(self):
        gsc = build_gsc_index([
            {"query": "thanksgiving 2026", "clicks": 1, "impressions": 50000, "ctr": 0.02, "position": 4.0},
            {"query": "niche term", "clicks": 0, "impressions": 50, "ctr": 0, "position": 20.0},
        ])
        gaps = top_gsc_gaps(gsc, limit=5)
        self.assertTrue(gaps)
        self.assertIn("thanksgiving", gaps[0]["query"])


if __name__ == "__main__":
    unittest.main()
