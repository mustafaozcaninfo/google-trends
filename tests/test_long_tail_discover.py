import unittest
from unittest.mock import Mock

from google_autocomplete import AutocompleteService, Suggestion
from long_tail_discover import (
    accept_autocomplete_suggestion,
    build_probes,
    dedupe_rows,
    extends_seed,
    is_junk_autocomplete,
    specificity_score,
)


class LongTailDiscoverTests(unittest.TestCase):
    def test_build_probes_includes_alphabet(self):
        probes = build_probes("sample ballot 2026", alphabet=True, question_prefixes=True, tail_space=True)
        kinds = {p[1] for p in probes}
        self.assertIn("seed", kinds)
        self.assertIn("tail", kinds)
        self.assertIn("a:t", kinds)
        self.assertIn("q:how", kinds)
        self.assertEqual(sum(1 for p in probes if p[1].startswith("a:")), 26)

    def test_build_probes_includes_digits(self):
        probes = build_probes("clipart", alphabet=False, question_prefixes=False, tail_space=False, digits=True)
        tags = {p[1] for p in probes}
        self.assertIn("n:0", tags)
        self.assertIn("n:9", tags)
        self.assertEqual(sum(1 for p in probes if p[1].startswith("n:")), 10)

    def test_extends_seed(self):
        self.assertTrue(extends_seed("sample ballot 2026 texas", "sample ballot 2026"))
        self.assertFalse(extends_seed("completely unrelated topic", "sample ballot 2026"))

    def test_dedupe_keeps_higher_relevance(self):
        rows = dedupe_rows([
            {"query": "Sample Ballot 2026 Texas", "relevance": 400, "source": "seed"},
            {"query": "sample ballot 2026 texas", "relevance": 550, "source": "a:t"},
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["relevance"], 550)

    def test_discover_long_tail_mock(self):
        import tempfile
        from pathlib import Path
        fetch = Mock(side_effect=lambda q, **_: [
            Suggestion(f"{q.strip()} texas county", 580),
            Suggestion("unrelated movies", 600),
        ])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "ac.sqlite3"
        svc = AutocompleteService(path, fetch=fetch, min_interval=0, ttl=60)
        rows, stats = svc.discover_long_tail(
            ["sample ballot 2026"], alphabet=False, question_prefixes=False, tail_space=False, min_words=3,
        )
        self.assertTrue(any("texas" in r["query"] for r in rows))
        self.assertFalse(any("unrelated" in r["query"] for r in rows))
        self.assertGreaterEqual(stats["probes"], 1)

    def test_junk_url_rejected(self):
        self.assertTrue(is_junk_autocomplete("https://calendar.google.com/"))
        self.assertFalse(
            accept_autocomplete_suggestion(
                "https://calendar.google.com/",
                seed="calendar",
                min_words=3,
                min_relevance=0,
                relevance=600,
            )
        )
        self.assertTrue(
            accept_autocomplete_suggestion(
                "how calendar was created",
                seed="calendar",
                min_words=4,
                min_relevance=0,
                relevance=600,
            )
        )

    def test_specificity_scores_county_higher(self):
        self.assertGreater(
            specificity_score("sample ballot 2026 tarrant county texas"),
            specificity_score("sample ballot 2026"),
        )


if __name__ == "__main__":
    unittest.main()
