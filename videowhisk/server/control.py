import asyncio
import logging

from . import messagebus, utils
from ..common import messages, protocol


log = logging.getLogger(__name__)


_allowed_types = (
    messages.SetAudioSource,
    messages.SetVideoSource,
)


class ControlServerProtocol(protocol.ControlProtocol):
    def __init__(self, server):
        super().__init__()
        self.server = server

    def connection_made(self, transport):
        super().connection_made(transport)
        self.server.send_initial_messages(self)

    def connection_lost(self, exc):
        if exc is not None:
            log.warning("Error on lost connection: %r", exc)
        self.server.connection_lost(self)

    def message_received(self, msg):
        if not isinstance(msg, _allowed_types):
            log.warning("Received unexpected message on control channel: %r", msg)
            return
        self.server._loop.create_task(self.server._bus.post(msg))


class ControlServer:

    def __init__(self, config, bus, loop):
        self._config = config
        self._bus = bus
        self._loop = loop

        self._connections = set()
        self._local_port = 0
        self._server = None
        self._start_server_task = self._loop.create_task(self.start_server())

    async def start_server(self):
        hostname, port = self._config.control_addr
        self._server = await self._loop.create_server(
            self.make_protocol, hostname, port)

    async def close(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        await utils.cancel_task(self._start_server_task)
        for protocol in list(self._connections):
            if protocol.transport is not None:
                protocol.transport.close()

    async def local_port(self):
        await self._start_server_task
        return self._server.sockets[0].getsockname()[1]

    def make_protocol(self):
        protocol = ControlServerProtocol(self)
        self._connections.add(protocol)
        return protocol

    def send_initial_messages(self, protocol):
        pass

    def connection_lost(self, protocol):
        self._connections.discard(protocol)
