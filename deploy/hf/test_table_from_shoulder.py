import unittest

from table_from_shoulder import table_y_from_shoulder_ratio


class TableFromShoulderTests(unittest.TestCase):
    def test_three_eighths_remaining_span(self):
        self.assertAlmostEqual(table_y_from_shoulder_ratio(0.24), 0.525)
        self.assertAlmostEqual(table_y_from_shoulder_ratio(0.30), 0.5625)
        self.assertAlmostEqual(table_y_from_shoulder_ratio(0.40), 0.625)

    def test_missing_shoulder(self):
        self.assertIsNone(table_y_from_shoulder_ratio(None))
        self.assertIsNone(table_y_from_shoulder_ratio(float("nan")))


if __name__ == "__main__":
    unittest.main()
