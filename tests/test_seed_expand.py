import unittest

from motors import MOTOR_FREE
from seed_expand import parse_seed_input


class SeedExpandTests(unittest.TestCase):
    def test_free_mode_only_extra(self):
        seeds = parse_seed_input(MOTOR_FREE, "foo bar, baz qux", root_words=False, include_motor_pack=False)
        self.assertEqual(seeds, ["foo bar", "baz qux"])

    def test_free_mode_ignores_motor_even_if_flag_true(self):
        seeds = parse_seed_input(MOTOR_FREE, "only mine", root_words=False, include_motor_pack=True)
        self.assertEqual(seeds, ["only mine"])

    def test_pack_plus_extra(self):
        seeds = parse_seed_input("Holidays & dates", "custom seed", root_words=False, include_motor_pack=True)
        self.assertIn("thanksgiving 2026", seeds)
        self.assertIn("custom seed", seeds)


if __name__ == "__main__":
    unittest.main()
