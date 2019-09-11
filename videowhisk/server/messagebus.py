import asyncio
import logging

from . import utils


log = logging.getLogger(__name__)


class MessageBus:
    def __init__(self, loop):
        self._loop = loop
        self._closed = False
        self._post_queue = asyncio.Queue(loop=self._loop)
        self._consumers = []
        self._run_task = self._loop.create_task(self.run())

    async def close(self):
        if self._closed:
            return
        self._closed = True
        await self._post_queue.join()
        await utils.cancel_task(self._run_task)
        for c in self._consumers:
            await c.close()

    async def run(self):
        while True:
            message = await self._post_queue.get()
            consumers = [c for c in self._consumers
                         if isinstance(message, c.types)]
            for c in consumers:
                if c.closed:
                    continue
                await c.queue.put(message)
            self._post_queue.task_done()

    async def post(self, message):
        if self._closed:
            log.warning("Attempt to send message %r on closed bus", message)
            return
        await self._post_queue.put(message)

    def add_consumer(self, types, consumer):
        queue = asyncio.Queue(loop=self._loop)
        task = self._loop.create_task(consumer(queue))
        self._consumers.append(Consumer(queue, task, types))


class Consumer:
    __slots__ = ("queue", "task", "types", "closed")

    def __init__(self, queue, task, types):
        self.queue = queue
        self.task = task
        self.types = types
        self.closed = False

    async def close(self):
        self.closed = True
        await self.queue.join()
        await utils.cancel_task(self.task)
