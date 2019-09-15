import asyncio
import signal
import unittest

import aiohttp
import asyncio_glib
from gi.repository import Gst

from videowhisk.common import messages
from videowhisk.server import config, server


class ServerTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio_glib.GLibEventLoop()
        self.loop.add_signal_handler(signal.SIGINT, self.loop.stop)
        self.config = config.Config()
        self.config.read_string("""
[server]
host = 127.0.0.1
""")
        self.server = server.Server(self.config, self.loop)

    def tearDown(self):
        self.loop.run_until_complete(self.server.close())
        self.loop.close()

    def make_sender(self, source):
        port = self.server.sources.local_port()
        pipeline = Gst.parse_launch("""
            {}
            matroskamux name=mux !
            tcpclientsink host=127.0.0.1 port={}
        """.format(source, port))
        self.addCleanup(pipeline.set_state, Gst.State.NULL)
        return pipeline

    def test_server(self):
        # Watch for new sources
        source_messages = []
        source_future = self.loop.create_future()
        async def source_consumer(queue):
            while True:
                message = await queue.get()
                source_messages.append(message)
                if len(source_messages) == 3:
                    source_future.set_result(None)
                queue.task_done()
        self.server.bus.add_consumer(messages.SourceMessage, source_consumer)
        # Create input sources
        sender = self.make_sender("""
            videotestsrc ! {} ! mux.
        """.format(self.config.video_caps.to_string()))
        sender.set_state(Gst.State.PLAYING)

        sender = self.make_sender("""
            videotestsrc ! {} ! mux.
        """.format(self.config.video_caps.to_string()))
        sender.set_state(Gst.State.PLAYING)

        sender = self.make_sender("""
            audiotestsrc freq=440 ! {} ! mux.
        """.format(self.config.audio_caps.to_string()))
        sender.set_state(Gst.State.PLAYING)

        self.loop.run_until_complete(source_future)

        # configure mixers
        amix_future = self.loop.create_future()
        vmix_future = self.loop.create_future()
        async def mixer_consumer(queue):
            while True:
                message = await queue.get()
                if isinstance(message, messages.AudioMixStatus):
                    if message.active_source == "c2.audio_0":
                        amix_future.set_result(None)
                if isinstance(message, messages.VideoMixStatus):
                    if (message.composite_mode == "picture-in-picture" and
                        message.source_a == "c0.video_0" and
                        message.source_b == "c1.video_0"):
                        vmix_future.set_result(None)
                queue.task_done()
        self.server.bus.add_consumer(
            (messages.AudioMixStatus, messages.VideoMixStatus),
            mixer_consumer)

        self.loop.create_task(self.server.bus.post(
            messages.SetAudioSource("c2.audio_0")))
        self.loop.create_task(self.server.bus.post(
            messages.SetVideoSource("picture-in-picture", "c0.video_0", "c1.video_0")))
        self.loop.run_until_complete(amix_future)
        amix_future.result()
        self.loop.run_until_complete(vmix_future)
        vmix_future.result()

        output_url = "http://127.0.0.1:{}/output".format(
            self.server.outputs.local_port())

        # Try to connect to the muxed output
        headers = None
        body = None
        async def make_request():
            nonlocal headers, body
            async with aiohttp.ClientSession() as session:
                async with session.get(output_url) as response:
                    headers = response.headers
                    body = await response.content.read(100)
        self.loop.run_until_complete(make_request())
        self.assertEqual(headers["Content-Type"], "video/x-matroska")
        self.assertEqual(body[:4], b"\x1A\x45\xDF\xA3")

    def test_make_initial_messages(self):
        source_future = self.loop.create_future()
        async def source_consumer(queue):
            count = 0
            while True:
                message = await queue.get()
                count += 1
                if count == 2:
                    source_future.set_result(None)
                queue.task_done()
        self.server.bus.add_consumer(messages.SourceMessage, source_consumer)
        # Create input sources
        sender = self.make_sender("""
            audiotestsrc freq=440 ! {} ! mux.
            videotestsrc ! {} ! mux.
        """.format(self.config.audio_caps.to_string(),
                   self.config.video_caps.to_string()))
        sender.set_state(Gst.State.PLAYING)
        self.loop.run_until_complete(source_future)

        transport = asyncio.Transport({"sockname": ("myhostname", 4242)})
        msgs = self.server.make_initial_messages(transport)
        self.assertEqual(len(msgs), 5)
        mixercfg = msgs[0]
        self.assertIsInstance(mixercfg, messages.MixerConfig)
        self.assertEqual(mixercfg.control_addr,
                         ("myhostname", self.server.control.local_port()))
        self.assertEqual(mixercfg.clock_addr, ("myhostname", 0))
        self.assertEqual(mixercfg.avsource_addr,
                         ("myhostname", self.server.sources.local_port()))
        self.assertEqual(mixercfg.avoutput_uri,
                         "http://myhostname:{}".format(
                             self.server.outputs.local_port()))
        self.assertEqual(mixercfg.composite_modes,
                         sorted(self.config.composite_modes.keys()))
        self.assertEqual(mixercfg.video_caps,
                         self.config.video_caps.to_string())
        self.assertEqual(mixercfg.audio_caps,
                         self.config.audio_caps.to_string())

        self.assertIsInstance(msgs[1], messages.VideoSourceAdded)
        self.assertIsInstance(msgs[2], messages.AudioSourceAdded)
        self.assertIsInstance(msgs[3], messages.VideoMixStatus)
        self.assertIsInstance(msgs[4], messages.AudioMixStatus)
