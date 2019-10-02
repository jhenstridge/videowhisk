import asyncio
import logging
import socket

from gi.repository import GLib, Gst, GstNet

from ..common import messages, protocol


log = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    pass


class ControlClient(protocol.ControlProtocol):

    def __init__(self, cfg_future):
        super().__init__()
        self._cfg_future = cfg_future
        self.local_addr = None
        self._local_sources = set()

    def message_received(self, msg):
        if isinstance(msg, messages.MixerConfig):
            self._cfg_future.set_result(msg)
        elif isinstance(msg, (messages.VideoSourceAdded,
                              messages.AudioSourceAdded)):
            if (self.local_addr is not None and
                msg.remote_addr == self.local_addr):
                self._local_sources.add(msg.channel)
        elif isinstance(msg, (messages.VideoSourceRemoved,
                              messages.AudioSourceRemoved)):
            if (self.local_addr is not None and
                msg.remote_addr == self.local_addr):
                self._local_sources.remove(msg.channel)
        elif isinstance(msg, messages.AudioMixStatus):
            if msg.active_source in self._local_sources:
                print("Active audio source")
        elif isinstance(msg, messages.VideoMixStatus):
            if msg.source_a in self._local_sources:
                print("Active video A")
            if msg.source_b in self._local_sources:
                print("Active video B")


class IngestPipeline:

    def __init__(self, loop):
        self._loop = loop
        self._pipeline = None
        self._done = False
        self._done_future = self._loop.create_future()

    async def run(self, control_addr, *, video=(), video_test=(),
                  audio=(), audio_test=()):
        cfg_future = self._loop.create_future()
        _, protocol = await self._loop.create_connection(
            lambda: ControlClient(cfg_future),
            control_addr[0], control_addr[1], )
        cfg = await cfg_future

        log.info("Connecting to avsource server at %r", cfg.avsource_addr)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        await self._loop.sock_connect(sock, cfg.avsource_addr)
        protocol.local_addr = sock.getsockname()[:2]
        self._eos_future = self._loop.create_future()
        self.make_pipeline(cfg, sock, video=video, video_test=video_test,
                           audio=audio, audio_test=audio_test)
        try:
            await self._done_future
        finally:
            self.destroy_pipeline()

    def make_pipeline(self, cfg, sock, *, video=(), video_test=(),
                      audio=(), audio_test=()):
        log.info("Creating NetClientClock for address %r", cfg.clock_addr)
        clock = GstNet.NetClientClock.new(
            'videowhisk', cfg.clock_addr[0], cfg.clock_addr[1], 0)
        clock.wait_for_sync(Gst.CLOCK_TIME_NONE)

        self._pipeline = Gst.Pipeline()
        self._pipeline.use_clock(clock)

        mux = Gst.ElementFactory.make("matroskamux", "mux")
        sink = Gst.ElementFactory.make("fdsink", "sink")
        sink.props.fd = sock.fileno()
        sink.props.sync = True
        self._pipeline.add(mux, sink)
        mux.link(sink)

        video_caps = Gst.Caps.from_string(cfg.video_caps)
        audio_caps = Gst.Caps.from_string(cfg.audio_caps)

        for videosrc in video:
            src = Gst.ElementFactory.make("v4l2src")
            src.props.device = videosrc
            self._pipeline.add(src)
            src.link_filtered(mux, video_caps)

        for videosrc in video_test:
            src = Gst.ElementFactory.make("videotestsrc")
            src.props.pattern = videosrc
            self._pipeline.add(src)
            src.link_filtered(mux, video_caps)

        for audiosrc in audio:
            src = Gst.ElementFactory.make("alsasrc")
            src.props.device = audiosrc
            self._pipeline.add(src)
            src.link_filtered(mux, audio_caps)

        for audiosrc in audio_test:
            src = Gst.ElementFactory.make("audiotestsrc")
            src.props.wave = audiosrc
            self._pipeline.add(src)
            src.link_filtered(mux, audio_caps)

        bus = self._pipeline.get_bus()
        bus.add_watch(GLib.PRIORITY_DEFAULT, self.on_bus_message)

        self._pipeline.set_state(Gst.State.PLAYING)

    def destroy_pipeline(self):
        self._pipeline.set_state(Gst.State.NULL)
        bus = self._pipeline.get_bus()
        bus.remove_watch()
        self._pipeline = None

    def on_bus_message(self, bus, msg):
        if msg.type == Gst.MessageType.EOS:
            self.set_done(None)
        elif msg.type == Gst.MessageType.ERROR:
            (error, debug) = msg.parse_error()
            log.warning("Pipeline reported error: %s", error.message)
            if debug:
                log.info("    %s", debug)
            self.set_done(PipelineError(error.message))
        return True

    def set_done(self, error):
        if self._done:
            return
        self._done = True
        if error is not None:
            self._loop.call_soon_threadsafe(
                self._done_future.set_exception, error)
        else:
            self._loop.call_soon_threadsafe(
                self._done_future.set_result, None)
