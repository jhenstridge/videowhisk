import asyncio
import logging
import signal
import sys

from . import shell


logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()
loop.add_signal_handler(signal.SIGINT, loop.stop)

sh = shell.Shell((sys.argv[1], int(sys.argv[2])), loop)
task = loop.create_task(sh.cmdloop())
loop.run_forever()

task.cancel()
try:
    loop.run_until_complete(task)
except asyncio.CancelledError:
    pass
