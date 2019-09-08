from gi.repository import Gst

from . import config, utils
from ..common import messages


class VideoMix:
    def __init__(self, config, bus, loop):
        self._closed = False
        self._loop = loop
        self._config = config
        self._bus = bus
        bus.add_consumer((messages.VideoSourceMessage,
                          messages.SetVideoSource), self.handle_message)
        self._sources = {}
        self._composite_mode = "fullscreen"
        self._source_a = None
        self._source_b = None
        self.make_pipeline()

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self.destroy_pipeline()

    def make_pipeline(self):
        self._pipeline = Gst.Pipeline("videomix")
        self._mixer = Gst.ElementFactory.make("compositor")
        tee = Gst.ElementFactory.make("tee")
        queue = Gst.ElementFactory.make("queue")
        sink = Gst.ElementFactory.make("intervideosink")
        sink.props.channel = "videomix.output"
        self._pipeline.add(self._mixer, tee, queue, sink)
        self._mixer.link_filtered(tee, self._config.video_caps)
        tee.link(queue)
        queue.link(sink)
        self._pipeline.set_state(Gst.State.PLAYING)

    def destroy_pipeline(self):
        self._pipeline.set_state(Gst.State.NULL)
        # Don't bother closing each source: they should be cleaned up
        # when the pipeline is unrefed.
        self._sources.clear()
        self._mixer = None
        self._pipeline = None

    async def handle_message(self, queue):
        while True:
            message = await queue.get()
            if isinstance(message, messages.VideoSourceAdded):
                source = VideoMixSource(
                    self._config, self._pipeline, message.channel,
                    self._mixer, self._loop)
                self._sources[message.channel] = source
            elif isinstance(message, messages.VideoSourceRemoved):
                source = self._sources.pop(message.channel, None)
                if source is not None:
                    if self._source_a == source.channel:
                        self._source_a = None
                    if self._source_b == source.channel:
                        self._source_b = None
                    await source.close()
            elif isinstance(message, messages.SetVideoSource):
                self.handle_source_change(message)
            queue.task_done()
            await self._bus.post(self.make_video_mix_status())
            source = None

    def handle_source_change(self, message):
        # Validate requested changes, defaulting to current state.
        new_composite_mode = message.composite_mode
        if new_composite_mode not in self._config.composite_modes:
            new_composite_mode = self._composite_mode
        new_source_a = message.source_a
        if new_source_a not in self._sources:
            new_source_a = self._source_a
        new_source_b = message.source_b
        if new_source_b not in self._sources:
            new_source_b = self._source_b
        if new_source_b == new_source_a:
            new_source_b = None

        # If nothing has changed, we're done.
        if (new_composite_mode == self._composite_mode and
            new_source_a == self._source_a and
            new_source_b == self._source_b):
            return

        # Reset sources no longer in use
        old_sources = {self._source_a, self._source_b}.difference(
            {new_source_a, new_source_b})
        for source in old_sources:
            if source is not None:
                self._sources[source].reset_pad()

        info = self._config.composite_modes[new_composite_mode]

        # Update source_a
        if new_source_a is not None:
            self._sources[new_source_a].apply(info.a)

        # Update source_b
        if new_source_b is not None:
            self._sources[new_source_b].apply(info.b)

        self._composite_mode = new_composite_mode
        self._source_a = new_source_a
        self._source_b = new_source_b

    def make_video_mix_status(self):
        return messages.VideoMixStatus(
            self._composite_mode, self._source_a, self._source_b)


class VideoMixSource:
    def __init__(self, config, pipeline, channel, mixer, loop):
        self._pipeline = pipeline
        self.channel = channel
        self._mixer = mixer
        self._loop = loop

        self._source = Gst.ElementFactory.make("intervideosrc")
        self._source.props.channel = "{}.mix".format(channel)
        self._filter = Gst.ElementFactory.make("capsfilter")
        self._filter.props.caps = config.video_caps
        self._queue = Gst.ElementFactory.make("queue")
        self._pipeline.add(self._source, self._filter, self._queue)
        self._source.link(self._filter)
        self._filter.link(self._queue)
        self._queue.link(self._mixer)
        self._sink_pad = self._queue.get_static_pad("src").get_peer()
        self.reset_pad()

        self._queue.sync_state_with_parent()
        self._filter.sync_state_with_parent()
        self._source.sync_state_with_parent()

    async def close(self):
        fut = self._loop.create_future()
        self._source.get_static_pad("src").add_probe(
            Gst.PadProbeType.BLOCK_DOWNSTREAM, self._source_pad_probe, fut)
        await fut

        # Stop the elements and remove them from the pipeline:
        for el in [self._source, self._filter, self._queue]:
            el.set_state(Gst.State.NULL)
            self._pipeline.remove(el)
        self._mixer.release_request_pad(self._sink_pad)

    def _source_pad_probe(self, pad, info, fut):
        pad.remove_probe(info.id)

        # Set new probe to wait for end of stream
        self._queue.get_static_pad("src").add_probe(
            Gst.PadProbeType.BLOCK | Gst.PadProbeType.EVENT_DOWNSTREAM,
            self._queue_pad_probe, fut)

        # Push EOS into element.  The pad probe will be triggered when
        # the EOS leaves the element and all data has drained.
        self._filter.get_static_pad("sink").send_event(Gst.Event.new_eos())
        return Gst.PadProbeReturn.OK

    def _queue_pad_probe(self, pad, info, fut):
        # Pass any non-EOS events on
        if info.get_event().type != Gst.EventType.EOS:
            return Gst.PadProbeReturn.PASS

        # All data has emptied from the elements we are going to
        # remove.  Drop the EOS event and signal the future.
        pad.remove_probe(info.id)
        self._loop.call_soon_threadsafe(fut.set_result, None)
        return Gst.PadProbeReturn.DROP

    def reset_pad(self):
        self.xpos = 0
        self.width = 0
        self.ypos = 0
        self.height = 0
        self.alpha = 0.0
        self.zorder = 0

    def apply(self, settings):
        self.xpos = settings.xpos
        self.width = settings.width
        self.ypos = settings.ypos
        self.height = settings.height
        self.alpha = settings.alpha
        self.zorder = settings.zorder

    xpos = utils.forward_prop("_sink_pad.props.xpos")
    width = utils.forward_prop("_sink_pad.props.width")
    ypos = utils.forward_prop("_sink_pad.props.ypos")
    height = utils.forward_prop("_sink_pad.props.height")
    alpha = utils.forward_prop("_sink_pad.props.alpha")
    zorder = utils.forward_prop("_sink_pad.props.zorder")
