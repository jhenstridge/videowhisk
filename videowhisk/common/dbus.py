import asyncio

from gi.repository import GLib, Gio


class Bus:

    def __init__(self, conn, loop):
        self._conn = conn
        self._loop = loop

    @property
    def unique_name(self):
        return self._conn.get_unique_name()

    async def get_object(self, bus_name, object_path, interface):
        loop = self._loop
        proxy_ready = loop.create_future()
        def ready_callback(obj, result):
            try:
                proxy = Gio.DBusProxy.new_finish(result)
            except GLib.Error as exc:
                loop.call_soon_threadsafe(proxy_ready.set_exception, exc)
                return
            loop.call_soon_threadsafe(proxy_ready.set_result, proxy)

        cancellable = Gio.Cancellable()
        Gio.DBusProxy.new(self._conn, Gio.DBusProxyFlags.NONE, None,
                          bus_name, object_path, interface,
                          cancellable, ready_callback)
        try:
            proxy = await proxy_ready
        except asyncio.CancelledError:
            cancellable.cancel()
            raise
        return Proxy(proxy, loop)


class Proxy:

    def __init__(self, proxy, loop):
        self._proxy = proxy
        self._loop = loop

    async def call_method(self, method_name, parameters):
        loop = self._loop
        result_ready = loop.create_future()
        def ready_callback(proxy, result):
            try:
                result = proxy.call_finish(result)
            except GLib.Error as exc:
                loop.call_soon_threadsafe(result_ready.set_exception, exc)
                return
            loop.call_soon_threadsafe(result_ready.set_result, result)

        cancellable = Gio.Cancellable()
        self._proxy.call(method_name, parameters,
                         Gio.DBusCallFlags.NONE, -1,
                         cancellable, ready_callback)
        try:
            return await result_ready
        except asyncio.CancelledError:
            cancellable.cancel()
            raise


async def _get_bus(bus_type, loop):
    bus_ready = loop.create_future()
    def ready_callback(obj, result):
        try:
            conn = Gio.bus_get_finish(result)
        except GLib.Error as exc:
            loop.call_soon_threadsafe(bus_ready.set_exception, exc)
            return
        loop.call_soon_threadsafe(bus_ready.set_result, conn)

    cancellable = Gio.Cancellable()
    Gio.bus_get(bus_type, cancellable, ready_callback)
    try:
        conn = await bus_ready
    except asyncio.CancelledError:
        cancellable.cancel()
        raise
    return Bus(conn, loop)


async def session_bus(loop):
    return await _get_bus(Gio.BusType.SESSION, loop)


async def system_bus(loop):
    return await _get_bus(Gio.BusType.SYSTEM, loop)
