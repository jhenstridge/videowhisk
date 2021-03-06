import asyncio
import unittest

from videowhisk.common import messages, protocol
from videowhisk.server import config, control, messagebus


class TestClientProtocol(protocol.ControlProtocol):

    def __init__(self, disconnect_future):
        super().__init__()
        self.disconnect = disconnect_future
        self.received = []

    def message_received(self, msg):
        self.received.append(msg)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        self.disconnect.set_result(exc)


class ControlTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.SelectorEventLoop()
        self.bus = messagebus.MessageBus(self.loop)
        self.config = config.Config()
        self.config.read_string("""
[server]
host = 127.0.0.1
""")
        self.server = control.ControlServer(self.config, self.bus, self.create_initial_messages, self.loop)
        self.initial_messages = []

    def tearDown(self):
        self.loop.run_until_complete(self.server.close())
        self.loop.run_until_complete(self.bus.close())
        self.loop.close()

    def create_initial_messages(self, transport):
        return self.initial_messages

    def test_receive_from_client(self):
        received = []
        future = self.loop.create_future()
        async def consumer(queue):
            while True:
                message = await queue.get()
                received.append(message)
                if len(received) == 1:
                    future.set_result(None)
                queue.task_done()
        self.bus.add_consumer(messages.SetVideoSource, consumer)

        disconnect_future = self.loop.create_future()
        transport, protocol = self.loop.run_until_complete(
            self.loop.create_connection(
                lambda: TestClientProtocol(disconnect_future),
                '127.0.0.1', self.server.local_port()))
        self.addCleanup(transport.close)

        protocol.send_message(messages.SetVideoSource("fullscreen", "a", "b"))
        self.loop.run_until_complete(future)

        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], messages.SetVideoSource)
        self.assertEqual(received[0].composite_mode, "fullscreen")
        self.assertEqual(received[0].source_a, "a")
        self.assertEqual(received[0].source_b, "b")

    def test_send_to_client(self):
        disconnect_future = self.loop.create_future()
        transport, protocol = self.loop.run_until_complete(
            self.loop.create_connection(
                lambda: TestClientProtocol(disconnect_future),
                '127.0.0.1', self.server.local_port()))
        self.addCleanup(transport.close)

        self.loop.run_until_complete(self.bus.post(
            messages.VideoSourceAdded("channel", ("hostname", 42))))
        self.loop.run_until_complete(self.server.close())
        self.loop.run_until_complete(disconnect_future)

        self.assertEqual(len(protocol.received), 1)
        self.assertIsInstance(protocol.received[0], messages.VideoSourceAdded)
        self.assertEqual(protocol.received[0].channel, "channel")
        self.assertEqual(protocol.received[0].remote_addr, ("hostname", 42))

    def test_sends_initial_messages(self):
        self.initial_messages = [
            messages.VideoSourceAdded("v1", ("host", 42)),
            messages.VideoSourceAdded("v2", ("host", 43)),
            messages.VideoMixStatus("picture-in-picture", "v1", "v2"),
        ]
        disconnect_future = self.loop.create_future()
        transport, protocol = self.loop.run_until_complete(
            self.loop.create_connection(
                lambda: TestClientProtocol(disconnect_future),
                '127.0.0.1', self.server.local_port()))
        self.addCleanup(transport.close)

        self.loop.run_until_complete(self.server.close())
        self.loop.run_until_complete(disconnect_future)

        self.assertEqual(len(protocol.received), 3)
        self.assertIsInstance(protocol.received[0], messages.VideoSourceAdded)
        self.assertIsInstance(protocol.received[1], messages.VideoSourceAdded)
        self.assertIsInstance(protocol.received[2], messages.VideoMixStatus)
