import asyncio
import socket

#from gi.repository import Gst
try:
    from http_parser.parser import HttpParser
except ImportError:
    from http_parser.pyparser import HttpParser

class AVOutputServer:

    def __init__(self, address, loop):
        self._loop = loop
        self._closed = False
        self._connections = {}
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._sock.bind(address)
        self._sock.listen(100)

        self._run_task = self._loop.create_task(self.run())

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._run_task.cancel()
        self._sock.close()

        for conn in list(self._connections.values()):
            await conn.close()

    def local_addr(self):
        return self._sock.getsockname()

    async def run(self):
        while True:
            (sock, address) = await self._loop.sock_accept(self._sock)
            conn = AVOutputConnection(sock, self)
            self._connections[sock.fileno()] = conn

    def _connection_ready(self, conn, path):
        print("Ready to serve", path)

    def _connection_closed(self, conn):
        self._connections.pop(conn.fileno())



class AVOutputConnection:
    def __init__(self, sock, server):
        self._closed = False
        self._sock = sock
        self._server = server
        self._loop = server._loop
        self._run_task = self._loop.create_task(self.run())

    def fileno(self):
        return self._sock.fileno()

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._server._connection_closed(self)
        self._sock.close()

    async def run(self):
        p = HttpParser(kind=0)
        while not p.is_message_complete():
            data = await self._loop.sock_recv(self._sock, 1024)
            if not data:
                break
            nparsed = p.execute(data, len(data))
            if nparsed != len(data):
                break

        self._sock.shutdown(socket.SHUT_RD)

        if p.is_message_complete() and p.get_method() == "GET":
            self._server._connection_ready(self, p.get_path())
            response = (b"HTTP/1.0 200 OK\r\n"
                        b"Content-Type: text/plain\r\n"
                        b"\r\n"
                        b"Good\n")
        else:
            response = (b"HTTP/1.0 400 Bad Request\r\n"
                        b"Content-Type: text/plain\r\n"
                        b"\r\n"
                        b"Bad\n")
        await self._loop.sock_sendall(self._sock, response)
        await self.close()
