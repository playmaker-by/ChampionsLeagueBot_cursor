import unittest

from scoring import calculate_points


class ScoringTests(unittest.TestCase):

    def test_exact_score(self):
        self.assertEqual(calculate_points(2, 1, 2, 1), (3, 1, 0, 0))

    def test_correct_difference(self):
        self.assertEqual(calculate_points(3, 1, 2, 0), (2, 0, 1, 0))

    def test_correct_outcome(self):
        self.assertEqual(calculate_points(1, 0, 3, 1), (1, 0, 0, 1))

    def test_draw_exact(self):
        self.assertEqual(calculate_points(1, 1, 1, 1), (3, 1, 0, 0))

    def test_draw_difference(self):
        self.assertEqual(calculate_points(0, 0, 2, 2), (2, 0, 1, 0))

    def test_wrong_draw_vs_win(self):
        self.assertEqual(calculate_points(1, 1, 2, 1), (0, 0, 0, 0))

    def test_away_win_outcome(self):
        self.assertEqual(calculate_points(0, 1, 1, 3), (1, 0, 0, 1))

    def test_complete_miss(self):
        self.assertEqual(calculate_points(0, 2, 2, 1), (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
