import os
import configparser

from gi.repository import Gst


class Config:

    def __init__(self):
        self._cfg = configparser.ConfigParser()
        self._cfg.read(os.path.join(os.path.dirname(__file__), "default.cfg"))
        self._update()

    def read(self, filename):
        self._cfg.read(filename)
        self._update()

    def _update(self):
        server = self._cfg["server"]
        self.audio_caps = Gst.Caps.from_string(server["audio_caps"])
        self.video_caps = Gst.Caps.from_string(server["video_caps"])
