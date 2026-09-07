import unittest

from utils import ParseError, parse_match_line, parse_score


class ParseScoreTests(unittest.TestCase):

    def test_colon(self):
        self.assertEqual(parse_score("2:1"), (2, 1))

    def test_dash(self):
        self.assertEqual(parse_score("2-1"), (2, 1))

    def test_spaces(self):
        self.assertEqual(parse_score(" 3 : 0 "), (3, 0))

    def test_invalid(self):
        with self.assertRaises(ParseError):
            parse_score("два ноль")


class ParseMatchLineTests(unittest.TestCase):

    def test_valid_line(self):
        parsed = parse_match_line("1|08.09.2026 21:00|АЕК Афины|ЛАСК")
        self.assertEqual(parsed["match_number"], 1)
        self.assertEqual(parsed["home_team"], "АЕК Афины")
        self.assertEqual(parsed["away_team"], "ЛАСК")
        self.assertEqual(parsed["kickoff_utc"], "2026-09-08 18:00:00")

    def test_same_teams(self):
        with self.assertRaises(ParseError):
            parse_match_line("1|08.09.2026 21:00|АЕК|АЕК")

    def test_bad_number(self):
        with self.assertRaises(ParseError):
            parse_match_line("19|08.09.2026 21:00|АЕК|ЛАСК")


if __name__ == "__main__":
    unittest.main()
