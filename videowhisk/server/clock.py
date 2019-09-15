from gi.repository import Gst, GstNet


def get_clock():
    return Gst.SystemClock.obtain()
