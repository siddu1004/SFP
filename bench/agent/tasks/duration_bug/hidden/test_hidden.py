import unittest

from duration import parse_duration


class Hidden(unittest.TestCase):
    def test_reported_cases(self):
        self.assertEqual(parse_duration("90"), 90)
        with self.assertRaises(ValueError):
            parse_duration("abc")

    def test_still_parses_units(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("45s"), 45)
        self.assertEqual(parse_duration("1h5m10s"), 3910)

    def test_empty_is_invalid(self):
        with self.assertRaises(ValueError):
            parse_duration("")

    def test_garbage_around_valid_parts_is_invalid(self):
        for bad in ("1x", "1h2x", "x1h", "1h30m!"):
            with self.assertRaises(ValueError, msg=bad):
                parse_duration(bad)

    def test_negative_is_invalid(self):
        with self.assertRaises(ValueError):
            parse_duration("-5")
