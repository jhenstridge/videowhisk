import asyncio
import signal
import sys

import asyncio_glib

# We need to initialise gst-python before importing our own code
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)

from . import config, server


asyncio.set_event_loop_policy(asyncio_glib.GLibEventLoopPolicy())
loop = asyncio.get_event_loop()
loop.add_signal_handler(signal.SIGINT, loop.stop)

config = config.Config()
server = server.Server(config, loop)

print("AVSourceServer on port {}".format(server.sources.local_addr()[1]))
print("AVOutputServer on port {}".format(server.outputs.local_addr()[1]))

loop.run_forever()
loop.run_until_complete(server.close())
