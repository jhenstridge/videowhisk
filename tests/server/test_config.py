import unittest

from gi.repository import Gst

from videowhisk.server import config


class ConfigTests(unittest.TestCase):

    def test_defaults(self):
        cfg = config.Config()
        self.assertIsInstance(cfg.audio_caps, Gst.Caps)
        self.assertEqual(cfg.audio_caps.get_size(), 1)
        struct = cfg.audio_caps.get_structure(0)
        self.assertEqual(struct.get_name(), "audio/x-raw")
        self.assertEqual(struct.get_value("format"), "S16LE")
        self.assertEqual(struct.get_value("channels"), 2)
        self.assertEqual(struct.get_value("layout"), "interleaved")
        self.assertEqual(struct.get_value("rate"), 48000)

        self.assertIsInstance(cfg.video_caps, Gst.Caps)
        self.assertEqual(cfg.video_caps.get_size(), 1)
        struct = cfg.video_caps.get_structure(0)
        self.assertEqual(struct.get_name(), "video/x-raw")
        self.assertEqual(struct.get_value("format"), "I420")
        self.assertEqual(struct.get_value("width"), 1920)
        self.assertEqual(struct.get_value("height"), 1080)
        self.assertEqual(struct.get_value("framerate"), Gst.Fraction(25, 1))
        self.assertEqual(struct.get_value("pixel-aspect-ratio"),
                         Gst.Fraction(1, 1))
        self.assertEqual(struct.get_value("interlace-mode"), "progressive")

        self.assertEqual(cfg.avsource_addr, ("0.0.0.0", 0))
        self.assertEqual(cfg.avoutput_addr, ("0.0.0.0", 0))

    def test_read_string(self):
        cfg = config.Config()
        cfg.read_string("""
[server]
video_caps = video/x-raw,format=I420,width=100,height=100,framerate=25/1,pixel-aspect-ratio=1/1,interlace-mode=progressive
host = 127.0.0.1
""")
        struct = cfg.video_caps.get_structure(0)
        self.assertEqual(struct.get_value("width"), 100)
        self.assertEqual(struct.get_value("height"), 100)

        self.assertEqual(cfg.avsource_addr, ("127.0.0.1", 0))
        self.assertEqual(cfg.avoutput_addr, ("127.0.0.1", 0))
