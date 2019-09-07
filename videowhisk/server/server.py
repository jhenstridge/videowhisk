
from . import messagebus, avsource, audiomix, videomix, avoutput


class Server:
    """Composes the various components of the mixing server"""

    def __init__(self, config, loop):
        self.loop = loop
        self.config = config
        self.bus = messagebus.MessageBus(loop)
        self.audiomix = audiomix.AudioMix(config, self.bus, loop)
        self.videomix = videomix.VideoMix(config, self.bus, loop)
        self.outputs = avoutput.AVOutputServer(config, self.bus, loop)
        self.sources = avsource.AVSourceServer(config, self.bus, loop)

    async def close(self):
        await self.outputs.close()
        await self.audiomix.close()
        await self.videomix.close()
        await self.sources.close()
        await self.bus.close()
