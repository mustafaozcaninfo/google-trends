#!/usr/bin/env python3
"""Live smoke checks — RSS, trending bundle, scan pipeline (minimal network)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CACHE = ROOT / ".cache"


class LiveSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geo = "US"

    def test_imports_dashboard_stack(self):
        import trending_service
        import trends_layer
        import motor_scan
        import dashboard_ui
        import interest_config

        self.assertTrue(hasattr(trending_service, "fetch_trending_bundle"))
        self.assertTrue(hasattr(trends_layer, "fetch_interest_map"))
        self.assertIn("render_landing", dashboard_ui.__all__)

    def test_rss_live(self):
        from trending_service import TrendingService, normalize_rss_trends

        def rss(geo):
            from trendspyg import download_google_trends_rss

            return download_google_trends_rss(geo=geo, normalize=True)

        svc = TrendingService(CACHE)
        pack = svc.fetch_rss(self.geo, rss)
        self.assertFalse(pack.get("error"), pack.get("error"))
        trends = normalize_rss_trends(pack)
        self.assertGreaterEqual(len(trends), 1, "RSS boş")
        self.assertTrue(trends[0].get("keyword"))
        self.assertIn("volume_min", trends[0])

    def test_bundle_auto_no_chrome_unless_cache(self):
        from trending_service import TrendingService, fetch_trending_bundle

        def rss(geo):
            from trendspyg import download_google_trends_rss

            return download_google_trends_rss(geo=geo, normalize=True)

        svc = TrendingService(CACHE)
        def _csv_unused(**_kwargs):
            raise AssertionError("auto should use cache, not Chrome")

        bundle = fetch_trending_bundle(
            svc, self.geo, mode="auto", hours=24, fetch_rss=rss, fetch_csv=_csv_unused,
        )
        self.assertIn(bundle.get("primary"), ("rss", "full"))
        self.assertGreater(len(bundle.get("trends") or []), 0)
        self.assertIsInstance(bundle.get("index"), dict)

    def test_full_cache_if_present(self):
        from trending_service import TrendingService

        svc = TrendingService(CACHE)
        cached = svc.load_full_cache(self.geo, 24)
        if not cached or not cached.get("trends"):
            self.skipTest("Tam liste önbelleği yok — sidebar’dan bir kez indir")
        self.assertGreater(len(cached["trends"]), 20, "Tam liste çok kısa")
        first = cached["trends"][0]
        self.assertIn("volume_min", first)
        self.assertIn("keyword", first)

    def test_motor_scan_quick_live(self):
        from related_queries import RelatedQueriesService
        from trending_service import TrendingService, fetch_trending_bundle
        import motor_scan

        def rss(geo):
            from trendspyg import download_google_trends_rss

            return download_google_trends_rss(geo=geo, normalize=True)

        def get_trendspy():
            from trendspy import Trends

            return Trends()

        bundle = fetch_trending_bundle(
            TrendingService(CACHE),
            self.geo,
            mode="auto",
            hours=24,
            fetch_rss=rss,
            fetch_csv=None,
        )
        seeds = ["thanksgiving 2026"]
        kw = (bundle.get("trends") or [{}])[0].get("keyword")
        if kw:
            seeds = [kw]

        payload = motor_scan.run_motor_scan(
            seeds,
            geo=self.geo,
            related_service=RelatedQueriesService(CACHE / "related.sqlite3"),
            get_trendspy=get_trendspy,
            get_trending_rss=rss,
            cache_dir=CACHE,
            trending_service=TrendingService(CACHE),
            scan_mode="quick",
            min_words=3,
            run_interest=True,
            interest_timeframe="now 1-d",
            use_trending_as_seeds=False,
            trending_mode="auto",
        )
        self.assertIn("rows", payload)
        self.assertGreater(payload["motor_meta"]["autocomplete_count"], 0)
        self.assertIn("trending_bundle", payload)
        self.assertIn("interest_timeframe", payload["motor_meta"])
        if payload["motor_meta"].get("interest_error"):
            self.skipTest(f"Interest rate limit: {payload['motor_meta']['interest_error']}")
        self.assertGreater(payload["motor_meta"].get("interest_checked", 0), 0)

    def test_single_word_free_scan_live(self):
        """Serbest mod: tek seed (ör. calendar), paket yok, interest kapalı."""
        from motors import MOTOR_FREE
        from related_queries import RelatedQueriesService
        from seed_expand import parse_seed_input
        import motor_scan

        def rss(geo):
            from trendspyg import download_google_trends_rss

            return download_google_trends_rss(geo=geo, normalize=True)

        def get_trendspy():
            from trendspy import Trends

            return Trends()

        seeds = parse_seed_input(
            MOTOR_FREE,
            "calendar",
            root_words=False,
            include_motor_pack=False,
        )
        self.assertEqual(seeds, ["calendar"])

        payload = motor_scan.run_motor_scan(
            seeds,
            geo=self.geo,
            related_service=RelatedQueriesService(CACHE / "related.sqlite3"),
            get_trendspy=get_trendspy,
            get_trending_rss=rss,
            cache_dir=CACHE,
            scan_mode="deep",
            min_words=4,
            run_interest=False,
            use_trending_as_seeds=False,
            trending_mode="auto",
        )
        self.assertEqual(payload.get("seeds"), ["calendar"])
        meta = payload["motor_meta"]
        self.assertEqual(meta["pipeline"]["step1_seeds"], 1)
        self.assertEqual(meta["pipeline"]["step1_seeds_with_roots"], 1)
        self.assertGreater(meta["autocomplete_count"], 0)
        rows = payload.get("rows") or []
        self.assertGreater(len(rows), 0)
        long_tail = [
            r
            for r in rows
            if len(((r.get("query") or "").strip()).split()) >= 4
            and "calendar" in (r.get("query") or "").lower()
        ]
        self.assertGreater(
            len(long_tail),
            0,
            "En az bir 4+ kelimelik calendar long-tail bekleniyor",
        )

    def test_landing_table_no_limit(self):
        import inspect
        import dashboard_ui

        src = inspect.getsource(dashboard_ui.render_landing)
        self.assertNotIn("display_limit", src)
        self.assertNotIn("[:display_limit]", src)
        self.assertIn("_trends_to_table", src)


def main():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(LiveSmokeTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    report = {
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "ok": result.wasSuccessful(),
    }
    print("\nSMOKE_JSON:", json.dumps(report))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
