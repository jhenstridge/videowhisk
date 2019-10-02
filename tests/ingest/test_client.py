import unittest

from videowhisk.ingest import client


class ClientTests(unittest.TestCase):

    def test_parse_args(self):
        cli = client.Client(None)

        args = cli.parse_args(["ingest", "--host", "foo", "--port", "42"])
        self.assertEqual(args.host, "foo")
        self.assertEqual(args.port, 42)
        self.assertEqual(args.video, [])
        self.assertEqual(args.video_test, [])
        self.assertEqual(args.audio, [])
        self.assertEqual(args.audio_test, [])

        args = cli.parse_args(["ingest", "--video=/dev/video2", "--audio", "--video-test", "--audio-test=white-noise"])
        self.assertEqual(args.host, None)
        self.assertEqual(args.port, None)
        self.assertEqual(args.video, ["/dev/video2"])
        self.assertEqual(args.video_test, ["smpte"])
        self.assertEqual(args.audio, ["default"])
        self.assertEqual(args.audio_test, ["white-noise"])
