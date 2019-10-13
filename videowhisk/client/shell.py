import asyncio
import readline
import sys

from ..common import messages, protocol


class ControlClient(protocol.ControlProtocol):

    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.mixer_cfg = None
        self.audio_sources = {}
        self.video_sources = {}
        self.audio_status = None
        self.video_status = None

    def message_received(self, msg):
        if isinstance(msg, messages.MixerConfig):
            self.mixer_cfg = msg
        elif isinstance(msg, messages.AudioSourceAdded):
            self.audio_sources[msg.channel] = msg
        elif isinstance(msg, messages.AudioSourceRemoved):
            self.audio_sources.pop(msg.channel, None)
        elif isinstance(msg, messages.VideoSourceAdded):
            self.video_sources[msg.channel] = msg
        elif isinstance(msg, messages.VideoSourceRemoved):
            self.video_sources.pop(msg.channel, None)
        elif isinstance(msg, messages.AudioMixStatus):
            self.audio_status = msg
        elif isinstance(msg, messages.VideoMixStatus):
            self.video_status = msg

    def connection_lost(self, exc):
        self.loop.stop()


class Shell:

    def __init__(self, control_addr, loop):
        self.control_addr = control_addr
        self.loop = loop
        self.protocol = None

    async def readline(self, prompt):
        return await self.loop.run_in_executor(None, input, prompt)

    async def cmdloop(self):
        _, self.protocol = await self.loop.create_connection(
            lambda: ControlClient(self.loop),
            self.control_addr[0], self.control_addr[1])
        while True:
            line = await self.readline("> ")
            args = line.split()
            if len(args) == 0: continue

            command = args.pop(0).replace('-', '_')
            handler = getattr(self, "do_{}".format(command), None)
            if handler is None:
                print("No such command: {}".format(command), file=sys.stderr)
                continue

            try:
                await handler(args)
            except SystemExit:
                self.loop.stop()
                return
            except Exception as exc:
                print("error {}: {}".format(exc.__class__.__name__, str(exc)),
                      file=sys.stderr)

    async def do_quit(self, args):
        sys.exit()

    async def do_list_audio(self, args):
        for name in sorted(self.protocol.audio_sources.keys()):
            print(name)

    async def do_list_video(self, args):
        for name in sorted(self.protocol.video_sources.keys()):
            print(name)

    async def do_set_video(self, args):
        mode, source_a, source_b = args
        if mode not in self.protocol.mixer_cfg.composite_modes:
            raise RuntimeError("unknown composite mode {}".format(mode))
        if source_a == '-':
            source_a = None
        elif source_a not in self.protocol.video_sources:
            raise RuntimeError("unknown video source {}".format(source_a))
        if source_b == '-':
            source_b = None
        elif source_b not in self.protocol.video_sources:
            raise RuntimeError("unknown video source {}".format(source_b))
        self.protocol.send_message(messages.SetVideoSource(
            mode, source_a, source_b))

    async def do_set_audio(self, args):
        source, = args
        if source == '-':
            source = None
        elif source not in self.protocol.audio_sources:
            raise RuntimeError("unknown audio source {}".format(source))
        self.protocol.send_message(messages.SetAudioSource(source))
