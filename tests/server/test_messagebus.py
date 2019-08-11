import asyncio
import unittest

from videowhisk.server import messagebus


class MessageOne(messagebus.Message):
    pass

class MessageTwo(messagebus.Message):
    pass


class MessageBusTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.SelectorEventLoop()

    def tearDown(self):
        self.loop.close()

    def test_send_with_no_consumers(self):
        bus = messagebus.MessageBus(self.loop)
        async def post_then_close():
            await bus.post(MessageOne())
            await bus.close()
        task = self.loop.create_task(post_then_close())
        self.loop.run_until_complete(task)
        task.done()

    def test_consumers_receive_filtered_messages(self):
        bus = messagebus.MessageBus(self.loop)

        consumer1_messages = []
        async def consumer1(queue):
            while True:
                consumer1_messages.append(await queue.get())
                queue.task_done()
        bus.add_consumer(MessageOne, consumer1)

        consumer2_messages = []
        async def consumer2(queue):
            while True:
                consumer2_messages.append(await queue.get())
                queue.task_done()
        bus.add_consumer(MessageTwo, consumer2)

        # Accept any messagebus.Message subclass
        consumer3_messages = []
        async def consumer3(queue):
            while True:
                consumer3_messages.append(await queue.get())
                queue.task_done()
        bus.add_consumer(messagebus.Message, consumer3)

        # Accept the two message types
        consumer4_messages = []
        async def consumer4(queue):
            while True:
                consumer4_messages.append(await queue.get())
                queue.task_done()
        bus.add_consumer((MessageOne, MessageTwo), consumer4)

        message1 = MessageOne()
        message2 = MessageTwo()
        async def post_then_close():
            await bus.post(message1)
            await bus.post(message2)
            await bus.close()
        task = self.loop.create_task(post_then_close())
        self.loop.run_until_complete(task)
        task.done()

        self.assertEqual(consumer1_messages, [message1])
        self.assertEqual(consumer2_messages, [message2])
        self.assertEqual(consumer3_messages, [message1, message2])
        self.assertEqual(consumer4_messages, [message1, message2])
