import unittest

from football_api import api_datetime_to_storage


class FootballApiTests(unittest.TestCase):

    def test_api_datetime_is_stored_as_utc(self):
        self.assertEqual(
            api_datetime_to_storage("2026-09-08T19:45:00Z"),
            "2026-09-08 19:45:00",
        )

    def test_api_datetime_with_offset_is_normalized(self):
        self.assertEqual(
            api_datetime_to_storage("2026-09-08T21:45:00+02:00"),
            "2026-09-08 19:45:00",
        )


if __name__ == "__main__":
    unittest.main()
