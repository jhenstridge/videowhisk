import asyncio
import socket

from gi.repository import GLib, Gst

from . import messagebus

class AVSourceServer:

    def __init__(self, config, bus, loop):
        self._loop = loop
        self._closed = False
        self._config = config
        self._bus = bus
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._sock.bind(config.avsource_addr)
        self._sock.listen(100)
        self._connections = {}
        self._run_task = self._loop.create_task(self.run())

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._run_task.cancel()
        self._sock.close()
        for conn in list(self._connections.values()):
            await conn.close()

    def local_addr(self):
        return self._sock.getsockname()

    async def run(self):
        counter = 0
        while True:
            (sock, address) = await self._loop.sock_accept(self._sock)
            # We never send data to the AV source
            sock.shutdown(socket.SHUT_WR)
            conn = AVSourceConnection(self, "c{}".format(counter), sock, address)
            self._connections[conn.name] = conn
            conn.start()
            counter += 1

    def _connection_closed(self, conn):
        del self._connections[conn.name]


class AVSourceConnection:
    def __init__(self, server, name, sock, address):
        self._server = server
        self._loop = server._loop
        self._closed = False
        self.name = name
        self._sock = sock
        self._address = address
        self.audio_sources = []
        self.video_sources = []
        self.make_pipeline()

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self.destroy_pipeline()
        self._sock.close()
        self._server._connection_closed(self)
        for channel in self.audio_sources:
            await self._server._bus.post(messagebus.AudioSourceRemoved(
                channel, self._address))
        for channel in self.video_sources:
            await self._server._bus.post(messagebus.VideoSourceRemoved(
                channel, self._address))

    def make_pipeline(self):
        self._pipeline = Gst.Pipeline(self.name)
        self._pipeline.use_clock(Gst.SystemClock.obtain())

        fdsrc = Gst.ElementFactory.make("fdsrc", "fdsrc")
        fdsrc.props.fd = self._sock.fileno()
        fdsrc.props.blocksize = 1048576
        queue = Gst.ElementFactory.make("queue", "srcqueue")

        self._demux = Gst.ElementFactory.make("matroskademux", "demux")
        self._demux_signal_id = self._demux.connect('pad-added', self.on_demux_pad_added)

        self._pipeline.add(fdsrc, queue, self._demux)
        fdsrc.link(queue)
        queue.link(self._demux)

        bus = self._pipeline.get_bus()
        bus.add_watch(GLib.PRIORITY_DEFAULT, self.on_bus_message)

    def destroy_pipeline(self):
        self._pipeline.set_state(Gst.State.NULL)
        self._demux.disconnect(self._demux_signal_id)
        self._demux = None
        bus = self._pipeline.get_bus()
        bus.remove_watch()
        self._pipeline = None

    def start(self):
        self._pipeline.set_state(Gst.State.PLAYING)

    def on_bus_message(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            self._loop.call_soon_threadsafe(
                self._loop.create_task, self.close())
        elif message.type == Gst.MessageType.ERROR:
            (error, debug) = message.parse_error()
            print("Bus error:", error, debug)
            self._loop.call_soon_threadsafe(
                self._loop.create_task, self.close())
        else:
            # ignore other messages
            pass
        return True

    def on_demux_pad_added(self, demux, src_pad):
        caps = src_pad.query_caps(None)
        if caps.can_intersect(self._server._config.audio_caps):
            channel = "{}.{}".format(self.name, src_pad.get_name())
            self.make_sink(src_pad, "interaudiosink", channel)
            self._loop.call_soon_threadsafe(
                self._loop.create_task,
                self.audio_source_added(channel))
        elif caps.can_intersect(self._server._config.video_caps):
            channel = "{}.{}".format(self.name, src_pad.get_name())
            self.make_sink(src_pad, "intervideosink", channel)
            self._loop.call_soon_threadsafe(
                self._loop.create_task,
                self.video_source_added(channel))
        else:
            # By not connecting to the pad, we'll trigger a bus error
            # that will close the connection.
            print("Got unknown pad with caps {}".format(caps.to_string()))

    def make_sink(self, src_pad, sinktype, channel):
        queue = Gst.ElementFactory.make("queue")
        tee = Gst.ElementFactory.make("tee")
        self._pipeline.add(queue, tee)
        src_pad.link(queue.get_static_pad("sink"))
        queue.link(tee)
        for output in ["monitor", "mix"]:
            tee_pad = tee.get_request_pad("src_%u")
            sink_queue = Gst.ElementFactory.make("queue")
            sink = Gst.ElementFactory.make(sinktype)
            sink.props.channel = "{}.{}".format(channel, output)
            self._pipeline.add(sink_queue, sink)
            tee_pad.link(sink_queue.get_static_pad("sink"))
            sink_queue.link(sink)
            sink_queue.sync_state_with_parent()
            sink.sync_state_with_parent()
        tee.sync_state_with_parent()
        queue.sync_state_with_parent()

    async def audio_source_added(self, channel):
        self.audio_sources.append(channel)
        await self._server._bus.post(messagebus.AudioSourceAdded(
            channel, self._address))

    async def video_source_added(self, channel):
        self.video_sources.append(channel)
        await self._server._bus.post(messagebus.VideoSourceAdded(
            channel, self._address))
