"""kwscraper bridge — mocked network."""

import unittest
from unittest.mock import patch

from kwscraper_bridge import harvest_alpha_rows


class KwscraperBridgeTests(unittest.TestCase):
    def test_harvest_alpha_rows_dedupes_and_filters(self):
        fake_pairs = [
            ("thanksgiving 2026", "thanksgiving 2026 printable calendar"),
            ("thanksgiving 2026", "thanksgiving 2026 printable calendar"),
            ("thanksgiving 2026", "thanksgiving 2026"),
        ]

        with patch("kwscraper.suggest.fetch_with_alpha", return_value=fake_pairs):
            rows, stats = harvest_alpha_rows(["thanksgiving 2026"], country="us", min_words=3)

        self.assertEqual(stats["seeds"], 1)
        self.assertEqual(stats["source"], "kwscraper")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["query"], "thanksgiving 2026 printable calendar")
        self.assertEqual(rows[0]["source"], "kwscraper:alpha")
