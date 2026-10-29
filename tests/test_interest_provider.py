import unittest

from interest_gate import InterestGate
from interest_provider import points_to_dataframe


class InterestProviderTests(unittest.TestCase):
    def test_points_to_dataframe(self):
        pts = [
            {"date": "2026-01-01T00:00:00+00:00", "value": 10},
            {"date": "2026-01-02T00:00:00+00:00", "value": 30},
        ]
        df = points_to_dataframe(pts, "foo")
        self.assertEqual(len(df), 2)
        self.assertAlmostEqual(float(df["foo"].iloc[-1]), 30.0)

    def test_gate_spacing(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            gate = InterestGate(Path(tmp) / "gate.json", min_interval_seconds=60)
            self.assertTrue(gate.allow_live())
            gate.mark_live()
            self.assertFalse(gate.allow_live())
            self.assertGreater(gate.seconds_until_allowed(), 0)


if __name__ == "__main__":
    unittest.main()
