import unittest

from videowhisk.common import messages


class MessagesTest(unittest.TestCase):

    def _test_source_message(self, cls):
        msg = cls("channel", ("address", 42))
        self.assertEqual(msg.channel, "channel")
        self.assertEqual(msg.remote_addr, ("address", 42))
        data = msg.serialise()
        msg2 = messages.deserialise(data)
        self.assertIsInstance(msg2, cls)
        self.assertEqual(msg2.channel, "channel")
        self.assertEqual(msg2.remote_addr, ("address", 42))

    def test_audio_source_added(self):
        self._test_source_message(messages.AudioSourceAdded)

    def test_audio_source_removed(self):
        self._test_source_message(messages.AudioSourceRemoved)

    def test_video_source_added(self):
        self._test_source_message(messages.VideoSourceAdded)

    def test_video_source_removed(self):
        self._test_source_message(messages.VideoSourceRemoved)

    def test_audio_mix_status(self):
        msg = messages.AudioMixStatus(
            "active", {"source1": 1.0, "source2": 0.0})
        self.assertEqual(msg.active_source, "active")
        self.assertEqual(msg.volumes, {"source1": 1.0, "source2": 0.0})
        data = msg.serialise()
        msg2 = messages.deserialise(data)
        self.assertIsInstance(msg2, messages.AudioMixStatus)
        self.assertEqual(msg2.active_source, "active")
        self.assertEqual(msg2.volumes, {"source1": 1.0, "source2": 0.0})

    def test_set_audio_source(self):
        msg = messages.SetAudioSource("active")
        self.assertEqual(msg.active_source, "active")
        data = msg.serialise()
        msg2 = messages.deserialise(data)
        self.assertIsInstance(msg2, messages.SetAudioSource)
        self.assertEqual(msg2.active_source, "active")

    def test_video_mix_status(self):
        msg = messages.VideoMixStatus("mode", "a", "b")
        self.assertEqual(msg.composite_mode, "mode")
        self.assertEqual(msg.source_a, "a")
        self.assertEqual(msg.source_b, "b")
        data = msg.serialise()
        msg2 = messages.deserialise(data)
        self.assertIsInstance(msg2, messages.VideoMixStatus)
        self.assertEqual(msg2.composite_mode, "mode")
        self.assertEqual(msg2.source_a, "a")
        self.assertEqual(msg2.source_b, "b")

    def test_set_video_source(self):
        msg = messages.SetVideoSource("mode", "a", "b")
        self.assertEqual(msg.composite_mode, "mode")
        self.assertEqual(msg.source_a, "a")
        self.assertEqual(msg.source_b, "b")
        data = msg.serialise()
        msg2 = messages.deserialise(data)
        self.assertIsInstance(msg2, messages.SetVideoSource)
        self.assertEqual(msg2.composite_mode, "mode")
        self.assertEqual(msg2.source_a, "a")
        self.assertEqual(msg2.source_b, "b")