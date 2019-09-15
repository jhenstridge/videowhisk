
from . import messagebus, clock, control, avsource, audiomix, videomix, avoutput
from ..common import messages


class Server:
    """Composes the various components of the mixing server"""

    def __init__(self, config, loop):
        self.loop = loop
        self.config = config
        self.bus = messagebus.MessageBus(loop)
        self.clock = clock.ClockServer(self.config)
        self.audiomix = audiomix.AudioMix(config, self.bus, loop)
        self.videomix = videomix.VideoMix(config, self.bus, loop)
        self.outputs = avoutput.AVOutputServer(config, self.bus, loop)
        self.sources = avsource.AVSourceServer(config, self.bus, loop)
        self.control = control.ControlServer(
            config, self.bus, self.make_initial_messages, loop)

    async def close(self):
        await self.control.close()
        await self.outputs.close()
        await self.audiomix.close()
        await self.videomix.close()
        await self.sources.close()
        await self.clock.close()
        await self.bus.close()

    def make_initial_messages(self, transport):
        # Use the local address matching the connection to the client
        local_addr = transport.get_extra_info("sockname")[0]
        msgs = [
            messages.MixerConfig(
                control_addr=(local_addr, self.control.local_port()),
                clock_addr=(local_addr, self.clock.local_port()),
                avsource_addr=(local_addr, self.sources.local_port()),
                avoutput_uri="http://{}:{}".format(
                    local_addr, self.outputs.local_port()),
                composite_modes=sorted(self.config.composite_modes.keys()),
                video_caps=self.config.video_caps.to_string(),
                audio_caps=self.config.audio_caps.to_string())
        ]
        msgs.extend(self.sources.make_source_messages())
        msgs.append(self.videomix.make_video_mix_status())
        msgs.append(self.audiomix.make_audio_mix_status())
        return msgs
