import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from google_autocomplete import AutocompleteService, parse_chrome_payload, Suggestion


class AutocompleteTests(unittest.TestCase):
    def test_parse_chrome_payload(self):
        sample = [
            "thanksgiving 2026",
            ["thanksgiving 2026 date", "thanksgiving 2026 nfl"],
            [], [],
            {"google:suggesttype": ["QUERY", "QUERY"],
             "google:suggestrelevance": [601, 550]},
        ]
        items = parse_chrome_payload(sample)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].text, "thanksgiving 2026 date")
        self.assertEqual(items[0].relevance, 601)

    def test_cache_and_cooldown(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        now = 1000.0
        fetch = Mock(return_value=[Suggestion("alpha", 600)])
        path = Path(tmp.name) / "ac.sqlite3"
        svc = AutocompleteService(path, fetch, lambda: now, min_interval=2.0)
        first = svc.get("seed", hl="en", gl="us")
        self.assertFalse(first.cached)
        self.assertEqual(first.suggestions[0].text, "alpha")
        second = svc.get("seed", hl="en", gl="us")
        self.assertTrue(second.cached)
        fetch.assert_called_once()
        now += 2.1
        svc.get("other", hl="en", gl="us")
        self.assertEqual(fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
