import asyncio
import socket

from gi.repository import Gst
try:
    from http_parser.parser import HttpParser
except ImportError:
    from http_parser.pyparser import HttpParser

from . import messagebus

class AVOutputServer:

    def __init__(self, config, bus, loop):
        self._loop = loop
        self._closed = False
        self._config = config
        bus.add_consumer(messagebus.SourceMessage, self.handle_message)
        self._connections = {}
        self._monitors = {}
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._sock.bind(config.avoutput_addr)
        self._sock.listen(100)

        self._run_task = self._loop.create_task(self.run())

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._run_task.cancel()
        self._sock.close()

        for conn in list(self._connections.values()):
            await conn.close()
        for monitor in list(self._monitors.values()):
            await monitor.close()

    def local_addr(self):
        return self._sock.getsockname()

    async def run(self):
        while True:
            (sock, address) = await self._loop.sock_accept(self._sock)
            conn = AVOutputConnection(sock, self)
            self._connections[sock.fileno()] = conn

    async def handle_message(self, queue):
        while True:
            message = await queue.get()
            if isinstance(message, messagebus.AudioSourceAdded):
                print("Adding audio monitor", message.channel)
                monitor = AVMonitor(message.channel, False, self)
                self._monitors[message.channel] = monitor
                monitor.start()
            elif isinstance(message, messagebus.VideoSourceAdded):
                print("Adding video monitor", message.channel)
                monitor = AVMonitor(message.channel, True, self)
                self._monitors[message.channel] = monitor
                monitor.start()
            elif isinstance(message, (messagebus.AudioSourceRemoved,
                                      messagebus.VideoSourceRemoved)):
                print("Removing monitor", message.channel)
                monitor = self._monitors.pop(message.channel, None)
                if monitor is not None:
                    await monitor.close()
            queue.task_done()

    def get_monitor(self, channel):
        return self._monitors.get(channel)

    def _connection_closed(self, conn):
        self._connections.pop(conn.fileno())

    async def _monitor_remove_fd(self, fileno):
        conn = self._connections.get(fileno)
        if conn is not None:
            await conn.close()


class AVMonitor:
    def __init__(self, channel, is_video, server):
        self._closed = False
        self._channel = channel
        self.is_video = is_video
        self._server = server
        self._loop = server._loop
        self._filenos = set()
        self.make_pipeline()

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self.destroy_pipeline()
        for fileno in self._filenos:
            await self._server._monitor_remove_fd(fileno)

    def make_pipeline(self):
        self._pipeline = Gst.Pipeline("monitor.{}".format(self._channel))
        self._pipeline.use_clock(Gst.SystemClock.obtain())

        if self.is_video:
            src = Gst.ElementFactory.make("intervideosrc")
            caps = self._server._config.video_caps
        else:
            src = Gst.ElementFactory.make("interaudiosrc")
            caps = self._server._config.audio_caps

        src.props.channel = "{}.{}".format(self._channel, "monitor")
        queue = Gst.ElementFactory.make("queue", "srcqueue")
        mux = Gst.ElementFactory.make("matroskamux")
        mux.props.streamable = True
        mux.props.writing_app = "videowhisk"
        self._sink = Gst.ElementFactory.make("multifdsink")
        self._sink.props.blocksize = 1048576
        self._sink.props.buffers_max = 500
        self._sink.props.sync_method = 1 # "next-keyframe"

        self._pipeline.add(src, queue, mux, self._sink)
        src.link_filtered(queue, caps)
        queue.link(mux)
        mux.link(self._sink)

        self._sink.connect("client-removed", self.on_client_removed)
        self._sink_signal_id = self._sink.connect(
            "client-fd-removed", self.on_client_fd_removed)

    def destroy_pipeline(self):
        self._pipeline.set_state(Gst.State.NULL)
        self._sink.disconnect(self._sink_signal_id)
        self._sink = None
        self._pipeline = None

    def start(self):
        self._pipeline.set_state(Gst.State.PLAYING)

    def add_fd(self, fileno):
        self._filenos.add(fileno)
        self._sink.emit("add", fileno)

    def on_client_removed(self, sink, fileno, status):
        print("client-removed", fileno, status.value_nick)

    def on_client_fd_removed(self, sink, fileno):
        self._filenos.remove(fileno)
        self._loop.call_soon_threadsafe(
            self._loop.create_task, self._server._monitor_remove_fd(fileno))


class AVOutputConnection:
    def __init__(self, sock, server):
        self._closed = False
        self._sock = sock
        self._server = server
        self._loop = server._loop
        self._run_task = self._loop.create_task(self.run())

    def fileno(self):
        return self._sock.fileno()

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._server._connection_closed(self)
        self._sock.close()

    async def run(self):
        p = HttpParser(kind=0)
        while not p.is_message_complete():
            data = await self._loop.sock_recv(self._sock, 1024)
            if not data:
                break
            nparsed = p.execute(data, len(data))
            if nparsed != len(data):
                break

        if not (p.is_message_complete() and p.get_method() in ("GET", "HEAD")):
            response = (b"HTTP/1.1 400 Bad Request\r\n"
                        b"Content-Type: text/plain\r\n"
                        b"\r\n"
                        b"Bad Request\n")
            await self._loop.sock_sendall(self._sock, response)
            await self.close()
            return

        channel = p.get_path().strip("/")
        monitor = self._server.get_monitor(channel)
        if monitor is None:
            response = (b"HTTP/1.1 404 Not Found\r\n"
                        b"Content-Type: text/plain\r\n"
                        b"\r\n")
            await self._loop.sock_sendall(self._sock, response)
            await self.close()
            return

        response = b"HTTP/1.1 200 OK\r\n"
        if monitor.is_video:
            response += b"Content-Type: video/x-matroska\r\n\r\n"
        else:
            response += b"Content-Type: audio/x-matroska\r\n\r\n"
        await self._loop.sock_sendall(self._sock, response)
        if p.get_method() == "HEAD":
            await self.close()
            return
        monitor.add_fd(self._sock.fileno())
