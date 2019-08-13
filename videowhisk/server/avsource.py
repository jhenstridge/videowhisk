import asyncio
import socket
import threading

from gi.repository import GLib, Gst

from . import messagebus

class AVSourceServer:

    def __init__(self, bus, address, loop):
        self._loop = loop
        self._bus = messagebus
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._sock.bind(address)
        self._sock.listen(100)
        self._connections = {}
        self.expected_audio_caps = Gst.Caps.from_string('audio/x-raw')
        self.expected_video_caps = Gst.Caps.from_string('video/x-raw')
        self._run_task = self._loop.create_task(self.run())

    async def close(self):
        self._run_task.cancel()
        self._sock.close()

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


class AVSourceConnection:
    def __init__(self, server, name, sock, address):
        self.server = server
        self.name = name
        self._sock = sock
        self._address = address
        self.make_pipeline()

    def close(self):
        print("closing")
        self.destroy_pipeline()
        self._sock.close()

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
            self.close()
        elif message.type == Gst.MessageType.ERROR:
            (error, debug) = message.parse_error()
            print("Bus error:", error, debug)
            self.close()
        else:
            # ignore other messages
            pass
        return True

    def on_demux_pad_added(self, demux, src_pad):
        caps = src_pad.query_caps(None)
        if caps.can_intersect(self.server.expected_audio_caps):
            queue = Gst.ElementFactory.make("queue", "aqueue")
            sink = Gst.ElementFactory.make("interaudiosink", "asink")
            sink.props.channel = "{}.{}".format(self.name, src_pad.get_name())
            self._pipeline.add(queue, sink)
            src_pad.link(queue.get_static_pad("sink"))
            queue.link(sink)
            queue.sync_state_with_parent()
            sink.sync_state_with_parent()
            self.server._loop.call_soon_threadsafe(
                self.source_added, 'audio', sink.props.channel)
        elif caps.can_intersect(self.server.expected_video_caps):
            queue = Gst.ElementFactory.make("queue", "vqueue")
            sink = Gst.ElementFactory.make("intervideosink", "vsink")
            sink.props.channel = "{}.{}".format(self.name, src_pad.get_name())
            self._pipeline.add(queue, sink)
            src_pad.link(queue.get_static_pad("sink"))
            queue.link(sink)
            queue.sync_state_with_parent()
            sink.sync_state_with_parent()
            self.server._loop.call_soon_threadsafe(
                self.source_added, 'video', sink.props.channel)
        else:
            # By not connecting to the pad, we'll trigger a bus error
            # that will close the connection.
            print("Got unknown pad with caps {}".format(caps.to_string()))

    def source_added(self, source_type, channel):
        print("Added source of type", source_type, "as", channel)
