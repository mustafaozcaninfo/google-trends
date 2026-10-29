import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from related_queries import RelatedQueriesService, explore_url
from trendspyg.exceptions import RateLimitError


class RelatedQueriesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 100000.0
        self.fetch = Mock(return_value={"related_queries": {
            "top": [{"query": "printable calendar", "value": 100}], "rising": []}})
        self.path = Path(self.tmp.name) / "cache.sqlite3"
        self.service = RelatedQueriesService(self.path, self.fetch, lambda: self.now)

    def test_scalar_and_exact_filters_and_persistent_cache(self):
        first = self.service.get(" calendar ", "tr", "today 3-m")
        self.fetch.assert_called_once_with("calendar", "TR", "today 3-m")
        self.assertFalse(first.cached)
        restarted = RelatedQueriesService(self.path, self.fetch, lambda: self.now)
        self.assertTrue(restarted.get("calendar", "TR", "today 3-m").cached)
        self.fetch.assert_called_once()
        self.now += 31
        self.service.get("calendar", "US", "today 3-m")
        self.assertEqual(self.fetch.call_count, 2)
        self.now += 31
        self.service.get("calendar", "US", "today 12-m")
        self.assertEqual(self.fetch.call_count, 3)

    def test_quota_cooldown_survives_restart_and_other_keywords(self):
        self.fetch.side_effect = RateLimitError("blocked")
        result = self.service.get("calendar", "US", "today 12-m")
        self.assertIsNone(result.data)
        self.assertEqual(result.retry_after, 1800)
        restarted = RelatedQueriesService(self.path, self.fetch, lambda: self.now)
        self.assertEqual(restarted.get("other", "TR", "today 3-m").retry_after, 1800)
        self.fetch.assert_called_once()
        self.now += 1801
        restarted.get("calendar", "US", "today 12-m")
        self.assertEqual(self.fetch.call_count, 2)

    def test_stale_data_retains_original_timestamp(self):
        self.service.get("calendar", "US", "today 12-m")
        self.now += 86401
        self.fetch.side_effect = RateLimitError("blocked")
        result = self.service.get("calendar", "US", "today 12-m")
        self.assertTrue(result.stale)
        self.assertEqual(result.fetched_at, 100000.0)
        self.assertEqual(result.data["top"][0]["value"], 100)
        self.assertIsNone(self.service.get("different", "US", "today 12-m").data)

    def test_empty_widget_is_not_cached_as_success_or_overwrite(self):
        self.service.get("calendar", "US", "today 12-m")
        self.now += 86401
        self.fetch.return_value = {"related_queries": {"top": [], "rising": []}}
        result = self.service.get("calendar", "US", "today 12-m")
        self.assertTrue(result.stale)
        self.assertEqual(result.fetched_at, 100000.0)
        self.assertEqual(result.retry_after, 120)

    def test_connection_failure_and_hourly_expiration(self):
        self.service.get("calendar", "US", "now 1-d")
        self.now += 3601
        self.fetch.side_effect = ConnectionError("offline")
        result = self.service.get("calendar", "US", "now 1-d")
        self.assertTrue(result.stale)
        self.assertEqual(result.retry_after, 120)

    def test_peek_is_filter_specific_and_never_fetches(self):
        self.assertIsNone(self.service.peek("calendar", "US", "today 12-m"))
        self.fetch.assert_not_called()
        self.service.get("calendar", "US", "today 12-m")
        self.assertFalse(self.service.peek("calendar", "US", "today 12-m").stale)
        self.now += 86401
        self.assertTrue(self.service.peek("calendar", "US", "today 12-m").stale)
        self.assertIsNone(self.service.peek("calendar", "TR", "today 12-m"))
        self.fetch.assert_called_once()

    def test_link_preserves_filters(self):
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(explore_url("a & b", "TR", "today 3-m")).query)
        self.assertEqual(query["q"], ["a & b"])
        self.assertEqual(query["geo"], ["TR"])
        self.assertEqual(query["date"], ["today 3-m"])


if __name__ == "__main__":
    unittest.main()
