import asyncio
import os
import unittest

import asyncio_glib
from gi.repository import GLib, Gio

from videowhisk.common import dbus


class DBusTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio_glib.GLibEventLoop()
        self.test_bus = Gio.TestDBus.new(Gio.TestDBusFlags.NONE)
        self.test_bus.up()

    def tearDown(self):
        self.test_bus.down()
        self.loop.close()

    def test_foo(self):
        async def call_method():
            bus = await dbus.session_bus(self.loop)
            obj = await bus.get_object("org.freedesktop.DBus",
                                       "/org/freedesktop/DBus",
                                       "org.freedesktop.DBus")
            result = await obj.call_method(
                "GetConnectionUnixProcessID",
                GLib.Variant("(s)", (bus.unique_name,)))
            return result.unpack()[0]

        pid = self.loop.run_until_complete(call_method())
        self.assertEqual(pid, os.getpid())
