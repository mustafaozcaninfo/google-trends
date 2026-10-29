import unittest

from keyword_individualize import preferred_canonical, subject_key


class KeywordIndividualizeTests(unittest.TestCase):
    def test_school_and_car_are_distinct_subjects(self):
        self.assertEqual(subject_key("school clipart free")[1], ("school",))
        self.assertEqual(subject_key("clipart car")[1], ("car",))
        self.assertNotEqual(subject_key("school clipart")[1], subject_key("car clipart")[1])

    def test_school_bus_not_merged_with_school(self):
        self.assertEqual(subject_key("clipart school bus")[1], ("bus", "school"))
        self.assertEqual(subject_key("school clipart")[1], ("school",))

    def test_prefer_subject_first_canonical(self):
        scores = {"school clipart free": 700, "clipart school": 600, "school clipart": 650}
        c = preferred_canonical(("school",), list(scores.keys()), scores)
        self.assertEqual(c, "school clipart")


if __name__ == "__main__":
    unittest.main()
