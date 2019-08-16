import asyncio
import signal
import unittest

import aiohttp
import asyncio_glib

from videowhisk.server import avoutput


class AVOutputTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio_glib.GLibEventLoop()
        self.loop.add_signal_handler(signal.SIGINT, self.loop.stop)
        self.server = avoutput.AVOutputServer(("127.0.0.1", 0), self.loop)

    def tearDown(self):
        self.loop.run_until_complete(self.server.close())

    def test_server(self):
        body = None
        async def make_request():
            nonlocal body
            async with aiohttp.ClientSession() as session:
                url = "http://127.0.0.1:{}/foo".format(
                    self.server.local_addr()[1])
                async with session.get(url) as response:
                    body = await response.text()
        self.loop.run_until_complete(make_request())
        self.assertEqual(body, "Good\n")
