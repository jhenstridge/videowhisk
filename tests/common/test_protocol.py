import asyncio
import unittest

from videowhisk.common import messages, protocol


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
        self.send_message(messages.AudioMixStatus("active", {}))
        self.send_message(messages.VideoMixStatus("mode", "a", "b"))
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
        port = server.sockets[0].getsockname()[1]

        async def client():
            transport, protocol = await self.loop.create_connection(
                lambda: TestClientProtocol(self.loop.create_future()),
                '127.0.0.1', port)
            await protocol.disconnect_future
            return protocol

        protocol = self.loop.run_until_complete(client())
        self.assertEqual(len(protocol.received_messages), 2)
        self.assertIsInstance(protocol.received_messages[0],
                              messages.AudioMixStatus)
        self.assertEqual(protocol.received_messages[0].active_source, "active")
        self.assertIsInstance(protocol.received_messages[1],
                              messages.VideoMixStatus)
        self.assertEqual(protocol.received_messages[1].composite_mode, "mode")
        self.assertEqual(protocol.received_messages[1].source_a, "a")
        self.assertEqual(protocol.received_messages[1].source_b, "b")

        server.close()
        self.loop.run_until_complete(server.wait_closed())
