import operator

from gi.repository import Gst

from . import messagebus

class AudioMix:
    def __init__(self, config, bus, loop):
        self._closed = False
        self._loop = loop
        self._config = config
        self._bus = bus
        bus.add_consumer((messagebus.AudioSourceMessage,
                          messagebus.SetAudioSource), self.handle_message)
        self._sources = {}
        self._active_source = None
        self.make_pipeline()

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self.destroy_pipeline()

    def make_pipeline(self):
        self._pipeline = Gst.Pipeline("audiomix")
        self._mixer = Gst.ElementFactory.make("audiomixer")
        tee = Gst.ElementFactory.make("tee")
        self._pipeline.add(self._mixer, tee)
        self._mixer.link_filtered(tee, self._config.audio_caps)
        for output in ["monitor", "mix"]:
            queue = Gst.ElementFactory.make("queue")
            sink = Gst.ElementFactory.make("interaudiosink")
            sink.props.channel = "audiomix.{}".format(output)
            self._pipeline.add(queue, sink)
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
            if isinstance(message, messagebus.AudioSourceAdded):
                source = AudioMixSource(
                    self._config, self._pipeline, message.channel,
                    self._mixer, self._loop)
                self._sources[message.channel] = source
            elif isinstance(message, messagebus.AudioSourceRemoved):
                source = self._sources.pop(message.channel, None)
                if source is not None:
                    await source.close()
                    if self._active_source == source.channel:
                        self._active_source = None
            elif isinstance(message, messagebus.SetAudioSource):
                if self._active_source != message.active_source and (
                        message.active_source is None or
                        message.active_source in self._sources):
                    if self._active_source is not None:
                        self._sources[self._active_source].mute = True
                    self._active_source = message.active_source
                    if self._active_source is not None:
                        self._sources[self._active_source].mute = False
            queue.task_done()
            await self._bus.post(self.make_audio_mix_status())
            source = None

    def make_audio_mix_status(self):
        volumes = {source.channel: source.volume
                   for source in self._sources.values()}
        return messagebus.AudioMixStatus(self._active_source, volumes)


class AudioMixSource:
    def __init__(self, config, pipeline, channel, mixer, loop):
        self._pipeline = pipeline
        self.channel = channel
        self._mixer = mixer
        self._loop = loop

        self._source = Gst.ElementFactory.make("interaudiosrc")
        self._source.props.channel = "{}.mix".format(channel)
        self._filter = Gst.ElementFactory.make("capsfilter")
        self._filter.props.caps = config.audio_caps
        self._queue = Gst.ElementFactory.make("queue")
        self._pipeline.add(self._source, self._filter, self._queue)
        self._source.link(self._filter)
        self._filter.link(self._queue)
        self._queue.link(self._mixer)
        self._sink_pad = self._queue.get_static_pad("src").get_peer()
        self._sink_pad.props.mute = True

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

    @property
    def mute(self):
        return self._sink_pad.props.mute

    @mute.setter
    def mute(self, value):
        self._sink_pad.props.mute = value

    @property
    def volume(self):
        return self._sink_pad.props.volume

    @volume.setter
    def volume(self, value):
        self._sink_pad.props.volume = value
