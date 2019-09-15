import asyncio
import unittest

from gi.repository import Gst

from videowhisk.server import clock, config


class ClockTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.SelectorEventLoop()
        self.config = config.Config()
        self.config.read_string("""
[server]
host = 127.0.0.1
""")

    def tearDown(self):
        self.loop.close()

    def test_get_clock(self):
        self.assertIsInstance(clock.get_clock(), Gst.Clock)

    def test_clock_server(self):
        server = clock.ClockServer(self.config)
        self.assertNotEqual(server.local_port(), 0)
        self.loop.run_until_complete(server.close())
