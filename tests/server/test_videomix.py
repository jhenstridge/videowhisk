import asyncio
import signal
import unittest

import asyncio_glib
from gi.repository import Gst

from videowhisk.common import messages
from videowhisk.server import videomix, config, messagebus


class VideoMixTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio_glib.GLibEventLoop()
        self.loop.set_debug(True)
        self.loop.add_signal_handler(signal.SIGINT, self.loop.stop)
        self.config = config.Config()
        self.bus = messagebus.MessageBus(self.loop)
        self.vmix = videomix.VideoMix(self.config, self.bus, self.loop)

    def tearDown(self):
        self.loop.run_until_complete(self.vmix.close())
        self.loop.run_until_complete(self.bus.close())
        self.loop.close()

    def make_video_source(self, channel="source.video"):
        pipeline = Gst.parse_launch("""
            videotestsrc !
            {} !
            intervideosink channel={}.mix
        """.format(self.config.video_caps.to_string(), channel))
        pipeline.set_state(Gst.State.PLAYING)
        self.addCleanup(pipeline.set_state, Gst.State.NULL)
        self.loop.create_task(self.bus.post(messages.VideoSourceAdded(channel, "127.0.0.1")))

    def test_add_remove_sources(self):
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                future.set_result(message)
                queue.task_done()
        self.bus.add_consumer(messages.VideoMixStatus, consumer)

        self.make_video_source()
        self.loop.run_until_complete(future)
        message = future.result()
        self.assertEqual(message.composite_mode, "fullscreen")
        self.assertEqual(message.source_a, None)
        self.assertEqual(message.source_b, None)
        self.assertIn("source.video", self.vmix._sources)

        future = self.loop.create_future()
        self.loop.create_task(self.bus.post(messages.VideoSourceRemoved("source.video", "127.0.0.1")))
        self.loop.run_until_complete(future)
        message = future.result()
        self.assertNotIn("source.video", self.vmix._sources)

    def test_set_video_source(self):
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                future.set_result(message)
                queue.task_done()
        self.bus.add_consumer(messages.VideoMixStatus, consumer)

        # Create sources
        self.make_video_source("source.video1")
        self.loop.run_until_complete(future)
        future = self.loop.create_future()
        self.make_video_source("source.video2")
        self.loop.run_until_complete(future)
        future = self.loop.create_future()
        self.make_video_source("source.video3")
        self.loop.run_until_complete(future)

        source_video1 = self.vmix._sources["source.video1"]
        source_video2 = self.vmix._sources["source.video2"]
        source_video3 = self.vmix._sources["source.video3"]

        # Reconfigure the video mixer
        future = self.loop.create_future()
        self.loop.create_task(self.bus.post(messages.SetVideoSource(
            "fullscreen", "source.video1", None)))
        self.loop.run_until_complete(future)
        message = future.result()
        self.assertEqual(message.composite_mode, "fullscreen")
        self.assertEqual(message.source_a, "source.video1")
        self.assertEqual(message.source_b, None)

        # Only video1 is visible
        self.assertEqual(source_video1.alpha, 1.0)
        self.assertEqual(source_video2.alpha, 0.0)
        self.assertEqual(source_video3.alpha, 0.0)

        # And video1 is drawn full screen
        self.assertEqual(source_video1.xpos, 0)
        self.assertEqual(source_video1.width, 1920)
        self.assertEqual(source_video1.ypos, 0)
        self.assertEqual(source_video1.height, 1080)

        # Reconfigure video mixer into PIP mode
        future = self.loop.create_future()
        self.loop.create_task(self.bus.post(messages.SetVideoSource(
            "picture-in-picture", "source.video2", "source.video3")))
        self.loop.run_until_complete(future)
        message = future.result()
        self.assertEqual(message.composite_mode, "picture-in-picture")
        self.assertEqual(message.source_a, "source.video2")
        self.assertEqual(message.source_b, "source.video3")

        # Now video2 and video3 are visible
        self.assertEqual(source_video1.alpha, 0.0)
        self.assertEqual(source_video2.alpha, 1.0)
        self.assertEqual(source_video3.alpha, 1.0)

        # And video2 is full screen
        self.assertEqual(source_video2.xpos, 0)
        self.assertEqual(source_video2.width, 1920)
        self.assertEqual(source_video2.ypos, 0)
        self.assertEqual(source_video2.height, 1080)
        self.assertEqual(source_video2.zorder, 1)

        # With video3 drawn on top
        self.assertEqual(source_video3.xpos, 1421)
        self.assertEqual(source_video3.width, 480)
        self.assertEqual(source_video3.ypos, 800)
        self.assertEqual(source_video3.height, 270)
        self.assertEqual(source_video3.zorder, 2)
