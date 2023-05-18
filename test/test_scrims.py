import unittest
from datetime import datetime
from unittest import TestCase

import pytz

import scrimbot


class SettingsTests(TestCase):

    def test_overlap(self):
        one = scrimbot.Scrim(data={'time': datetime(2022, 10, 10, 14, 0).timestamp()}, timezone=pytz.UTC)
        two = scrimbot.Scrim(data={'time': datetime(2022, 10, 10, 14, 59).timestamp()}, timezone=pytz.UTC)

        self.assertTrue(one.overlaps_with(two))
        self.assertTrue(two.overlaps_with(one))

    def test_doesnt_overlap(self):
        one = scrimbot.Scrim(data={'time': datetime(2022, 10, 10, 14, 0).timestamp()}, timezone=pytz.UTC)
        two = scrimbot.Scrim(data={'time': datetime(2022, 10, 10, 15, 0).timestamp()}, timezone=pytz.UTC)

        self.assertFalse(one.overlaps_with(two))
        self.assertFalse(two.overlaps_with(one))


if __name__ == '__main__':
    unittest.main()
