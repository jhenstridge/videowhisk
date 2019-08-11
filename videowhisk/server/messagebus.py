import asyncio


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
        self._run_task.cancel()
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
        assert not self._closed
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
        self.task.cancel()


class Message:
    __slots__ = ()
