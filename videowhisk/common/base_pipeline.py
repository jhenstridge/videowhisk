from gi.repository import Gst


class BasePipeline:

    def __init__(self, name=None):
        super().__init__()
        self.__pipeline_name = None
        self.__bus_eos_id = 0
        self.__bus_error_id = 0
        self.pipeline = None

    def make_pipeline(self):
        self.pipeline = Gst.Pipeline(self.__pipeline_name)
        self.set_clock()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        self.__bus_eos_id = bus.connect("message::eos", self.__on_eos)
        self.__bus_error_id = bus.connect("message::error", self.__on_error)

    def destroy_pipeline(self):
        self.pipeline.set_state(Gst.State.NULL)
        bus = self.pipeline.get_bus()
        bus.remove_watch()
        if self.__bus_eos_id != 0:
            bus.disconnect(self.__bus_eos_id)
        if self.__bus_error_id != 0:
            bus.disconnect(self.__bus_error_id)
        self.pipeline = None

    def set_clock(self):
        raise NotImplementedError()

    def __on_eos(self, bus, msg):
        self.on_bus_eos()

    def on_bus_eos(self):
        raise NotImplementedError()

    def __on_error(self, bus, msg):
        error, debug = msg.parse_error()
        self.on_bus_error(error, debug)

    def on_bus_error(self, error, debug):
        raise NotImplementedError()
