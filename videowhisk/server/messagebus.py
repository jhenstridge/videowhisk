import asyncio

from . import utils


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
        utils.cancel_task(self._run_task)
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
        utils.cancel_task(self.task)


class Message:
    __slots__ = ()


class SourceMessage(Message):
    __slots__ = ("channel", "remote_addr")

    def __init__(self, channel, remote_addr):
        self.channel = channel
        self.remote_addr = remote_addr


class AudioSourceMessage(SourceMessage):
    __slots__ = ()


class AudioSourceAdded(AudioSourceMessage):
    __slots__ = ()


class AudioSourceRemoved(AudioSourceMessage):
    __slots__ = ()


class VideoSourceMessage(SourceMessage):
    __slots__ = ()


class VideoSourceAdded(VideoSourceMessage):
    __slots__ = ()


class VideoSourceRemoved(VideoSourceMessage):
    __slots__ = ()


class AudioMixStatus(Message):
    __slots__ = ("active_source", "volumes")

    def __init__(self, active_source, volumes):
        self.active_source = active_source
        self.volumes = volumes


class SetAudioSource(Message):
    __slots__ = ("active_source",)

    def __init__(self, active_source):
        self.active_source = active_source
