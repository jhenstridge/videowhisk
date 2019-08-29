import asyncio
import signal
import unittest

import aiohttp
import asyncio_glib
from gi.repository import Gst

from videowhisk.server import avoutput, config, messagebus


class AVOutputTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio_glib.GLibEventLoop()
        self.loop.add_signal_handler(signal.SIGINT, self.loop.stop)
        self.config = config.Config()
        self.bus = messagebus.MessageBus(self.loop)
        self.server = avoutput.AVOutputServer(
            self.config, self.bus, ("127.0.0.1", 0), self.loop)

    def tearDown(self):
        self.loop.run_until_complete(self.server.close())
        self.loop.run_until_complete(self.bus.close())

    def make_audio_source(self):
        pipeline = Gst.parse_launch("""
            audiotestsrc freq=440 !
            {} !
            interaudiosink channel=source.audio
        """.format(self.config.audio_caps.to_string()))
        pipeline.set_state(Gst.State.PLAYING)
        self.addCleanup(pipeline.set_state, Gst.State.NULL)
        self.loop.create_task(self.bus.post(messagebus.AudioSourceAdded("source.audio", "127.0.0.1")))

    def make_video_source(self):
        pipeline = Gst.parse_launch("""
            videotestsrc !
            {} !
            intervideosink channel=source.video
        """.format(self.config.video_caps.to_string()))
        pipeline.set_state(Gst.State.PLAYING)
        self.addCleanup(pipeline.set_state, Gst.State.NULL)
        self.loop.create_task(self.bus.post(messagebus.VideoSourceAdded("source.video", "127.0.0.1")))

    def test_audio(self):
        self.make_audio_source()
        headers = None
        body = None
        async def make_request():
            nonlocal headers, body
            async with aiohttp.ClientSession() as session:
                url = "http://127.0.0.1:{}/source.audio".format(
                    self.server.local_addr()[1])
                async with session.get(url) as response:
                    headers = response.headers
                    body = await response.content.read(100)
        self.loop.run_until_complete(make_request())
        self.assertEqual(headers["Content-Type"], "audio/x-matroska")
        self.assertEqual(body[:4], b"\x1A\x45\xDF\xA3")

    def test_video(self):
        self.make_video_source()
        headers = None
        body = None
        async def make_request():
            nonlocal headers, body
            async with aiohttp.ClientSession() as session:
                url = "http://127.0.0.1:{}/source.video".format(
                    self.server.local_addr()[1])
                async with session.get(url) as response:
                    headers = response.headers
                    body = await response.content.read(100)
        self.loop.run_until_complete(make_request())
        self.assertEqual(headers["Content-Type"], "video/x-matroska")
        self.assertEqual(body[:4], b"\x1A\x45\xDF\xA3")
