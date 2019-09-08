import asyncio
import signal
import unittest

import asyncio_glib
from gi.repository import Gst

from videowhisk.common import messages
from videowhisk.server import avsource, config, messagebus

class AVSourceTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio_glib.GLibEventLoop()
        self.loop.add_signal_handler(signal.SIGINT, self.loop.stop)
        self.bus = messagebus.MessageBus(self.loop)
        self.config = config.Config()
        self.config.read_string("""
[server]
host = 127.0.0.1
""")
        self.server = avsource.AVSourceServer(
            self.config, self.bus, self.loop)

    def tearDown(self):
        self.loop.run_until_complete(self.server.close())
        self.loop.run_until_complete(self.bus.close())
        self.loop.close()

    def make_sender(self, source):
        port = self.server.local_addr()[1]
        pipeline = Gst.parse_launch("""
            {}
            matroskamux name=mux !
            tcpclientsink host=127.0.0.1 port={}
        """.format(source, port))
        self.addCleanup(pipeline.set_state, Gst.State.NULL)
        return pipeline

    def test_send_video(self):
        received = []
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                received.append(message)
                if len(received) == 1:
                    future.set_result(None)
                queue.task_done()
        self.bus.add_consumer(messages.SourceMessage, consumer)

        sender = self.make_sender("""
            videotestsrc ! {} ! mux.
        """.format(self.config.video_caps.to_string()))
        sender.set_state(Gst.State.PLAYING)
        self.loop.run_until_complete(future)
        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], messages.VideoSourceAdded)
        self.assertEqual(received[0].channel, "c0.video_0")

        received.clear()
        future = self.loop.create_future()
        sender.set_state(Gst.State.NULL)

        self.loop.run_until_complete(future)
        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], messages.VideoSourceRemoved)
        self.assertEqual(received[0].channel, "c0.video_0")

    def test_send_audio(self):
        received = []
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                received.append(message)
                if len(received) == 1:
                    future.set_result(None)
                queue.task_done()
        self.bus.add_consumer(messages.SourceMessage, consumer)

        sender = self.make_sender("""
            audiotestsrc freq=440 ! {} ! mux.
        """.format(self.config.audio_caps.to_string()))
        sender.set_state(Gst.State.PLAYING)
        self.loop.run_until_complete(future)
        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], messages.AudioSourceAdded)
        self.assertEqual(received[0].channel, "c0.audio_0")

        received.clear()
        future = self.loop.create_future()
        sender.set_state(Gst.State.NULL)

        self.loop.run_until_complete(future)
        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], messages.AudioSourceRemoved)
        self.assertEqual(received[0].channel, "c0.audio_0")

    def test_send_two_audio_streams(self):
        received = []
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                received.append(message)
                if len(received) == 2:
                    future.set_result(None)
                queue.task_done()
        self.bus.add_consumer(messages.SourceMessage, consumer)

        sender = self.make_sender("""
            audiotestsrc freq=440 ! {} ! mux.
            audiotestsrc freq=440 ! {} ! mux.
        """.format(self.config.audio_caps.to_string(),
                   self.config.audio_caps.to_string()))
        sender.set_state(Gst.State.PLAYING)
        self.loop.run_until_complete(future)
        self.assertEqual(len(received), 2)
        self.assertIsInstance(received[0], messages.AudioSourceAdded)
        self.assertEqual(received[0].channel, "c0.audio_0")
        self.assertIsInstance(received[1], messages.AudioSourceAdded)
        self.assertEqual(received[1].channel, "c0.audio_1")

        received.clear()
        future = self.loop.create_future()
        sender.set_state(Gst.State.NULL)

        self.loop.run_until_complete(future)
        self.assertEqual(len(received), 2)
        self.assertIsInstance(received[0], messages.AudioSourceRemoved)
        self.assertEqual(received[0].channel, "c0.audio_0")
        self.assertIsInstance(received[1], messages.AudioSourceRemoved)
        self.assertEqual(received[1].channel, "c0.audio_1")

    def test_send_audio_and_video(self):
        received = []
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                received.append(message)
                if len(received) == 2:
                    future.set_result(None)
                queue.task_done()
        self.bus.add_consumer(messages.SourceMessage, consumer)

        sender = self.make_sender("""
            audiotestsrc freq=440 ! {} ! mux.
            videotestsrc ! {} ! mux.
        """.format(self.config.audio_caps.to_string(),
                   self.config.video_caps.to_string()))
        sender.set_state(Gst.State.PLAYING)
        self.loop.run_until_complete(future)
        self.assertEqual(len(received), 2)
        self.assertIsInstance(received[0], messages.AudioSourceAdded)
        self.assertEqual(received[0].channel, "c0.audio_0")
        self.assertIsInstance(received[1], messages.VideoSourceAdded)
        self.assertEqual(received[1].channel, "c0.video_0")

        received.clear()
        future = self.loop.create_future()
        sender.set_state(Gst.State.NULL)

        self.loop.run_until_complete(future)
        self.assertEqual(len(received), 2)
        self.assertIsInstance(received[0], messages.AudioSourceRemoved)
        self.assertEqual(received[0].channel, "c0.audio_0")
        self.assertIsInstance(received[1], messages.VideoSourceRemoved)
        self.assertEqual(received[1].channel, "c0.video_0")
