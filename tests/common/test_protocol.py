import asyncio
import unittest

from videowhisk.common import protocol


class TestClientProtocol(protocol.ControlProtocol):

    def __init__(self, disconnect_future):
        super().__init__()
        self.disconnect_future = disconnect_future
        self.received_messages = []

    def message_received(self, msg):
        self.received_messages.append(msg)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        self.disconnect_future.set_result(exc)


class TestServerProtocol(protocol.ControlProtocol):

    def connection_made(self, transport):
        super().connection_made(transport)
        self.send_message({"key": "value"})
        self.send_message([1, 2, 3, 4])
        self.transport.close()


class ProtocolTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.SelectorEventLoop()

    def tearDown(self):
        self.loop.close()

    def test_send_and_receive(self):
        server = self.loop.run_until_complete(self.loop.create_server(
            TestServerProtocol, "127.0.0.1", 0))
        self.addCleanup(server.close)
        self.loop.run_until_complete(server.start_serving())
        port = server.sockets[0].getsockname()[1]

        async def client():
            transport, protocol = await self.loop.create_connection(
                lambda: TestClientProtocol(self.loop.create_future()),
                '127.0.0.1', port)
            await protocol.disconnect_future
            return protocol

        protocol = self.loop.run_until_complete(client())
        self.assertEqual(len(protocol.received_messages), 2)
        self.assertEqual(protocol.received_messages[0], {"key": "value"})
        self.assertEqual(protocol.received_messages[1], [1, 2, 3, 4])

        server.close()
        self.loop.run_until_complete(server.wait_closed())
