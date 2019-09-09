import asyncio
import json
import logging
import struct

from . import messages


log = logging.getLogger(__name__)


class ControlProtocol(asyncio.Protocol):
    """A simple protocol that sends and receives length prefixed JSON objects

    The format is inspired by the "native messaging" protocol from
    WebExtensions, but always uses big endian encoding for the lengths
    rather than the native byte order.
    """

    def __init__(self):
        super().__init__()
        self.have_length = False
        self.message_length = 0
        self.buffered = b""

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        if exc is not None:
            log.warning(...)

    def data_received(self, data):
        """Decode messages received over the wire."""
        self.buffered += data
        while True:
            if self.have_length:
                if len(self.buffered) < self.message_length:
                    break
                self._decode_message(self.buffered[:self.message_length])
                self.have_length = False
                self.buffered = self.buffered[self.message_length:]
                self.message_length = 0
            else:
                if len(self.buffered) < 4:
                    break
                (self.message_length,) = struct.unpack_from(">I", self.buffered)
                self.buffered = self.buffered[4:]
                self.have_length = True

    def _decode_message(self, data):
        try:
            msg = messages.deserialise(json.loads(data))
        except Exception:
            log.exception("Error decoding message:")
            return
        self.message_received(msg)

    def message_received(self, message):
        raise NotImplementedError

    def send_message(self, message):
        encoded = json.dumps(message.serialise()).encode("UTF-8")
        self.transport.write(struct.pack(">I", len(encoded)))
        self.transport.write(encoded)
