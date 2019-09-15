import unittest

from gi.repository import Gst

from videowhisk.server import clock


class ClockTests(unittest.TestCase):

    def test_get_clock(self):
        self.assertIsInstance(clock.get_clock(), Gst.Clock)
