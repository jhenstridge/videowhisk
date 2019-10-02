import argparse

from . import pipeline


class Client:

    def __init__(self, loop):
        self._loop = loop

    def parse_args(self, argv):
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", type=str)
        parser.add_argument("--port", type=int)
        parser.add_argument("--video", nargs="?", const="/dev/video0",
                            action="append", default=[], metavar="DEVICE",
                            help="A video source to ingest")
        parser.add_argument("--video-test", nargs="?", const="smpte",
                            action="append", default=[], metavar="PATTERN",
                            help="A video test source")
        parser.add_argument("--audio", nargs="?", const="default",
                            action="append", default=[], metavar="DEVICE",
                            help="An ALSA source to ingest")
        parser.add_argument("--audio-test", nargs="?", const="sine",
                            action="append", default=[], metavar="WAVE",
                            help="An audio test source")
        return parser.parse_args(argv[1:])

    async def run(self, args):
        ingest = pipeline.IngestPipeline(self._loop)
        try:
            await ingest.run((args.host, args.port),
                             video=args.video,
                             video_test=args.video_test,
                             audio=args.audio,
                             audio_test=args.audio_test)
        except pipeline.PipelineError:
            pass
