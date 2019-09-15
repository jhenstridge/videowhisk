from gi.repository import Gst, GstNet


def get_clock():
    return Gst.SystemClock.obtain()


class ClockServer:

    def __init__(self, config):
        self._closed = False
        address, port = config.clock_addr
        self._provider = GstNet.NetTimeProvider.new(get_clock(), address, port)

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._provider = None

    def local_port(self):
        assert not self._closed
        return self._provider.props.port
