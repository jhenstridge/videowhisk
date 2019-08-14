import asyncio
import signal
import subprocess
import unittest

import asyncio_glib

from videowhisk.server import avsource, messagebus

class AVSourceTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio_glib.GLibEventLoop()
        self.loop.add_signal_handler(signal.SIGINT, self.loop.stop)
        self.bus = messagebus.MessageBus(self.loop)
        self.server = avsource.AVSourceServer(
            self.bus, ('127.0.0.1', 0), self.loop)

    def tearDown(self):
        self.loop.run_until_complete(self.server.close())
        self.loop.run_until_complete(self.bus.close())
        self.loop.close()

    def make_sender(self, *pipeline):
        port = self.server.local_addr()[1]
        args = ["gst-launch-1.0"]
        args.extend(pipeline)
        args.extend(["matroskamux", "name=mux", "!", "tcpclientsink",
                     "host=127.0.0.1", "port={}".format(port)])
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL)
        self.addCleanup(proc.terminate)
        return proc

    def test_send_video(self):
        messages = []
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                messages.append(message)
                if len(messages) == 1:
                    future.set_result(None)
                queue.task_done()
        self.bus.add_consumer(messagebus.SourceMessage, consumer)

        proc = self.make_sender(
            "videotestsrc", "!",
            "video/x-raw,format=I420,width=100,height=100,framerate=60/1", "!"
            "mux.")
        self.loop.run_until_complete(future)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], messagebus.VideoSourceAdded)
        self.assertEqual(messages[0].channel, "c0.video_0")

        messages.clear()
        future = self.loop.create_future()
        proc.terminate()
        proc.wait()

        self.loop.run_until_complete(future)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], messagebus.VideoSourceRemoved)
        self.assertEqual(messages[0].channel, "c0.video_0")

    def test_send_audio(self):
        messages = []
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                messages.append(message)
                if len(messages) == 1:
                    future.set_result(None)
                queue.task_done()
        self.bus.add_consumer(messagebus.SourceMessage, consumer)

        proc = self.make_sender(
            "audiotestsrc", "freq=440", "!",
            "audio/x-raw,format=S16LE,channels=2,layout=interleaved,rate=48000", "!"
            "mux.")
        self.loop.run_until_complete(future)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], messagebus.AudioSourceAdded)
        self.assertEqual(messages[0].channel, "c0.audio_0")

        messages.clear()
        future = self.loop.create_future()
        proc.terminate()
        proc.wait()

        self.loop.run_until_complete(future)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], messagebus.AudioSourceRemoved)
        self.assertEqual(messages[0].channel, "c0.audio_0")

    def test_send_audio_and_video(self):
        messages = []
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                messages.append(message)
                if len(messages) == 2:
                    future.set_result(None)
                queue.task_done()
        self.bus.add_consumer(messagebus.SourceMessage, consumer)

        proc = self.make_sender(
            "audiotestsrc", "freq=440", "!",
            "audio/x-raw,format=S16LE,channels=2,layout=interleaved,rate=48000",
            "!", "mux.",
            "videotestsrc", "!",
            "video/x-raw,format=I420,width=100,height=100,framerate=60/1", "!"
            "mux.")
        self.loop.run_until_complete(future)
        self.assertEqual(len(messages), 2)
        self.assertIsInstance(messages[0], messagebus.AudioSourceAdded)
        self.assertEqual(messages[0].channel, "c0.audio_0")
        self.assertIsInstance(messages[1], messagebus.VideoSourceAdded)
        self.assertEqual(messages[1].channel, "c0.video_0")

        messages.clear()
        future = self.loop.create_future()
        proc.terminate()
        proc.wait()

        self.loop.run_until_complete(future)
        self.assertEqual(len(messages), 2)
        self.assertIsInstance(messages[0], messagebus.AudioSourceRemoved)
        self.assertEqual(messages[0].channel, "c0.audio_0")
        self.assertIsInstance(messages[1], messagebus.VideoSourceRemoved)
        self.assertEqual(messages[1].channel, "c0.video_0")