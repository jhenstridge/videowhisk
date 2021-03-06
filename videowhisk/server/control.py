import asyncio
import logging

from . import messagebus
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

    def __init__(self, config, bus, initial_message_factory, loop):
        self._config = config
        self._bus = bus
        self._initial_message_factory = initial_message_factory
        self._loop = loop
        self._closed = False

        bus.add_consumer(messages.Message, self.handle_message)

        self._connections = set()
        hostname, port = config.control_addr
        self._server = loop.run_until_complete(loop.create_server(
            self.make_protocol, hostname, port))

    async def start_server(self):
        hostname, port = self._config.control_addr
        self._server = await self._loop.create_server(
            self.make_protocol, hostname, port)

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._server.close()
        await self._server.wait_closed()
        for protocol in list(self._connections):
            if protocol.transport is not None:
                protocol.transport.close()

    def local_port(self):
        return self._server.sockets[0].getsockname()[1]

    def make_protocol(self):
        protocol = ControlServerProtocol(self)
        self._connections.add(protocol)
        return protocol

    async def handle_message(self, queue):
        while True:
            message = await queue.get()
            for protocol in self._connections:
                protocol.send_message(message)
            queue.task_done()

    def send_initial_messages(self, protocol):
        messages = self._initial_message_factory(protocol.transport)
        for message in messages:
            protocol.send_message(message)

    def connection_lost(self, protocol):
        self._connections.discard(protocol)
