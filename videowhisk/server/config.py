import os
import configparser
import collections

from gi.repository import Gst


CompositeMode = collections.namedtuple("CompositeMode", ["name", "a", "b"])
CompositeInput = collections.namedtuple(
    "CompositeInput", ["xpos", "width", "ypos", "height", "zorder", "alpha"])


def _decode_composite_mode(name, section, video_width, video_height):
    """Decode a composite mode configuration section"""
    a = _decode_composite_input(section, "a.", video_width, video_height)
    b = _decode_composite_input(section, "b.", video_width, video_height)
    return CompositeMode(name, a, b)


def _decode_composite_input(section, prefix, video_width, video_height):
    """Decode one of the inputs from a composite section"""
    xpos, width = _decode_dimension(
        section, prefix + "left", prefix + "width", prefix + "right",
        video_width)
    ypos, height = _decode_dimension(
        section, prefix + "top", prefix + "height", prefix + "bottom",
        video_height)
    zorder = section.getint(prefix + "zorder", 1)
    alpha = section.getfloat(prefix + "alpha", 1.0)
    return CompositeInput(xpos, width, ypos, height, zorder, alpha)

def _decode_dimension(section, start_prop, length_prop, end_prop, total):
    """Decode one of the dimensions for a composite input.

    The dimensions are specified by two of three properties specifying
    the start position, length, and end position, any of which can be
    specified as a percentage of the total dimension.

    The integer start position and length are returned.
    """
    if sum([section.get(prop) is not None
            for prop in [start_prop, length_prop, end_prop]]) != 2:
        raise ValueError("Only two of {}, {}, and {} should be set".format(
            start_prop, length_prop, end_prop))

    start = _decode_value(section.get(start_prop), total)
    length = _decode_value(section.get(length_prop), total)
    end = _decode_value(section.get(end_prop), total)

    if start is None:
        return total - end - length, length
    elif length is None:
        return start, total - start - end
    else:
        return start, length

def _decode_value(value, total):
    """Decode a value that might be a percentage."""
    if value is None:
        return None
    if value.endswith('%'):
        return int(value[:-1]) * total // 100
    else:
        return int(value)


class Config:

    def __init__(self):
        self._cfg = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
        self._cfg.read(os.path.join(os.path.dirname(__file__), "default.cfg"))
        self._update()

    def read_file(self, filename):
        self._cfg.read(filename)
        self._update()

    def read_string(self, data):
        self._cfg.read_string(data)
        self._update()

    def _update(self):
        server = self._cfg["server"]
        self.audio_caps = Gst.Caps.from_string(server["audio_caps"])
        self.video_caps = Gst.Caps.from_string(server["video_caps"])

        host = server["host"]
        if not host:
            # XXX: consider IPV6
            host = "0.0.0.0"
        self.avsource_addr = (host, server.getint("avsource_port"))
        self.avoutput_addr = (host, server.getint("avoutput_port"))

        struct = self.video_caps.get_structure(0)
        video_width = struct.get_value("width")
        video_height = struct.get_value("height")

        self.composite_modes = {}
        for section_name in self._cfg.sections():
            if not section_name.startswith("composite."):
                continue
            mode = section_name[len("composite."):]
            section = self._cfg[section_name]
            if section.getboolean("disabled"):
                continue
            self.composite_modes[mode] = _decode_composite_mode(
                mode, section, video_width, video_height)
