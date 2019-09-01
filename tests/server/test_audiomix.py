import asyncio
import signal
import unittest

import asyncio_glib
from gi.repository import Gst

from videowhisk.server import audiomix, config, messagebus


class AudioMixTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio_glib.GLibEventLoop()
        self.loop.set_debug(True)
        self.loop.add_signal_handler(signal.SIGINT, self.loop.stop)
        self.config = config.Config()
        self.bus = messagebus.MessageBus(self.loop)
        self.amix = audiomix.AudioMix(self.config, self.bus, self.loop)

    def tearDown(self):
        self.loop.run_until_complete(self.amix.close())
        self.loop.run_until_complete(self.bus.close())

    def make_audio_source(self):
        pipeline = Gst.parse_launch("""
            audiotestsrc freq=440 !
            {} !
            interaudiosink channel=source.audio.mix
        """.format(self.config.audio_caps.to_string()))
        pipeline.set_state(Gst.State.PLAYING)
        self.addCleanup(pipeline.set_state, Gst.State.NULL)
        self.loop.create_task(self.bus.post(messagebus.AudioSourceAdded("source.audio", "127.0.0.1")))

    def test_add_remove_sources(self):
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                future.set_result(message)
                queue.task_done()
        self.bus.add_consumer(messagebus.AudioMixStatus, consumer)

        self.make_audio_source()
        self.loop.run_until_complete(future)
        message = future.result()
        self.assertEqual(message.active_source, None)
        self.assertEqual(message.volumes, {"source.audio": 1.0})

        future = self.loop.create_future()
        self.loop.create_task(self.bus.post(messagebus.AudioSourceRemoved("source.audio", "127.0.0.1")))
        self.loop.run_until_complete(future)
        message = future.result()
        self.assertEqual(message.active_source, None)
        self.assertEqual(message.volumes, {})
