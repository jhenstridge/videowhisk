import json


class Message:
    __slots__ = ()

    message_type = None

    def serialise(self):
        raise NotImplementedError()

    @classmethod
    def deserialise(cls, data):
        raise NotImplementedError()


class MixerConfig(Message):
    __slots__ = ("control_addr", "clock_addr", "avsource_addr",
                 "composite_modes", "video_caps", "audio_caps",
                 "output_uri")
    message_type = "mixer-config"

    def __init__(self, control_addr, clock_addr, avsource_addr,
                 composite_modes, video_caps, audio_caps,
                 output_uri):
        self.control_addr = control_addr
        self.clock_addr = clock_addr
        self.avsource_addr = avsource_addr
        self.composite_modes = composite_modes
        self.video_caps = video_caps
        self.audio_caps = audio_caps
        self.output_uri = output_uri

    def serialise(self):
        return dict(
            type=self.message_type,
            control_addr=self.control_addr,
            clock_addr=self.clock_addr,
            avsource_addr=self.avsource_addr,
            composite_modes=self.composite_modes,
            video_caps=self.video_caps,
            audio_caps=self.audio_caps,
            output_uri=self.output_uri,
        )

    @classmethod
    def deserialise(cls, data):
        assert data["type"] == cls.message_type
        return cls(tuple(data["control_addr"]), tuple(data["clock_addr"]),
                   tuple(data["avsource_addr"]), data["composite_modes"],
                   data["video_caps"], data["audio_caps"],
                   data["output_uri"])


class SourceMessage(Message):
    __slots__ = ("channel", "remote_addr")

    def __init__(self, channel, remote_addr):
        self.channel = channel
        self.remote_addr = remote_addr

    def serialise(self):
        return dict(
            type=self.message_type,
            channel=self.channel,
            remote_addr=self.remote_addr[:2],
        )

    @classmethod
    def deserialise(cls, data):
        assert data["type"] == cls.message_type
        return cls(data["channel"], tuple(data["remote_addr"]))


class AudioSourceMessage(SourceMessage):
    __slots__ = ()


class AudioSourceAdded(AudioSourceMessage):
    __slots__ = ()
    message_type = "audio-source-added"


class AudioSourceRemoved(AudioSourceMessage):
    __slots__ = ()
    message_type = "audio-source-removed"


class VideoSourceMessage(SourceMessage):
    __slots__ = ()


class VideoSourceAdded(VideoSourceMessage):
    __slots__ = ()
    message_type = "video-source-added"


class VideoSourceRemoved(VideoSourceMessage):
    __slots__ = ()
    message_type = "video-source-removed"


class AudioMixStatus(Message):
    __slots__ = ("active_source", "volumes")
    message_type = "audio-mix-status"

    def __init__(self, active_source, volumes):
        self.active_source = active_source
        self.volumes = volumes

    def serialise(self):
        return dict(
            type=self.message_type,
            active_source=self.active_source,
            volumes=self.volumes,
        )

    @classmethod
    def deserialise(cls, data):
        assert data["type"] == cls.message_type
        return cls(data["active_source"], data["volumes"])


class SetAudioSource(Message):
    __slots__ = ("active_source",)
    message_type = "set-audio-source"

    def __init__(self, active_source):
        self.active_source = active_source

    def serialise(self):
        return dict(
            type=self.message_type,
            active_source=self.active_source,
        )

    @classmethod
    def deserialise(cls, data):
        assert data["type"] == cls.message_type
        return cls(data["active_source"])


class VideoMixStatus(Message):
    __slots__ = ("composite_mode", "source_a", "source_b")
    message_type = "video-mix-status"

    def __init__(self, composite_mode, source_a, source_b):
        self.composite_mode = composite_mode
        self.source_a = source_a
        self.source_b = source_b

    def serialise(self):
        return dict(
            type=self.message_type,
            composite_mode=self.composite_mode,
            source_a=self.source_a,
            source_b=self.source_b,
        )

    @classmethod
    def deserialise(cls, data):
        assert data["type"] == cls.message_type
        return cls(data["composite_mode"], data["source_a"], data["source_b"])


class SetVideoSource(Message):
    __slots__ = ("composite_mode", "source_a", "source_b")
    message_type = "set-video-source"

    def __init__(self, composite_mode, source_a, source_b):
        self.composite_mode = composite_mode
        self.source_a = source_a
        self.source_b = source_b

    def serialise(self):
        return dict(
            type=self.message_type,
            composite_mode=self.composite_mode,
            source_a=self.source_a,
            source_b=self.source_b,
        )

    @classmethod
    def deserialise(cls, data):
        assert data["type"] == cls.message_type
        return cls(data["composite_mode"], data["source_a"], data["source_b"])


_message_class_by_type = {
    cls.message_type: cls for cls in [
        MixerConfig,
        AudioSourceAdded,
        AudioSourceRemoved,
        VideoSourceAdded,
        VideoSourceRemoved,
        AudioMixStatus,
        SetAudioSource,
        VideoMixStatus,
        SetVideoSource,
    ]}


def deserialise(data):
    type = data.get("type")
    cls = _message_class_by_type[type]
    return cls.deserialise(data)
