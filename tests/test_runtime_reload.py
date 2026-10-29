"""A running Streamlit process must upgrade old service classes on rerun."""
import importlib
from pathlib import Path
import unittest

import related_queries
from streamlit.testing.v1 import AppTest


class RuntimeReloadTests(unittest.TestCase):
    def test_stale_import_without_peek_recovers(self):
        old_class = related_queries.RelatedQueriesService
        del old_class.peek
        self.addCleanup(importlib.reload, related_queries)
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
        app.radio[0].set_value('Uzun Kuyruk Araştırması').run()
        self.assertFalse(app.exception)
        self.assertTrue(hasattr(related_queries.RelatedQueriesService, 'peek'))
        self.assertIsNot(related_queries.RelatedQueriesService, old_class)
        self.assertGreater(len(app.dataframe), 0)
        app.run()
        self.assertFalse(app.exception)
