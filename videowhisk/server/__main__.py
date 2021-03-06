import asyncio
import logging
import signal
import sys

import asyncio_glib

# We need to initialise gst-python before importing our own code
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstNet', '1.0')
from gi.repository import Gst
Gst.init(None)

from . import config, server


logging.basicConfig(level=logging.INFO)

asyncio.set_event_loop_policy(asyncio_glib.GLibEventLoopPolicy())
loop = asyncio.get_event_loop()
loop.add_signal_handler(signal.SIGINT, loop.stop)

config = config.Config()
server = server.Server(config, loop)

print("ControlServer on port {}".format(server.control.local_port()))
print("AVSourceServer on port {}".format(server.sources.local_port()))
print("AVOutputServer on port {}".format(server.outputs.local_port()))

loop.run_forever()
loop.run_until_complete(server.close())
