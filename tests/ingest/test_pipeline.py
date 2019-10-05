import unittest

from gi.repository import Gst

from videowhisk.ingest import pipeline


class PipelineTests(unittest.TestCase):

    def test_choose_video_caps(self):
        target_caps = Gst.Caps.from_string(
            "video/x-raw,format=YUY2,width=1920,height=1080,framerate=30/1,pixel-aspect-ratio=1/1,interlace-mode=progressive")

        # EzCap 261 caps:
        source_caps = Gst.Caps.from_string("""
video/x-raw, format=(string)YUY2, width=(int)1920, height=(int)1080, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 };
video/x-raw, format=(string)YUY2, width=(int)1280, height=(int)1024, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 };
video/x-raw, format=(string)YUY2, width=(int)1440, height=(int)900, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 };
video/x-raw, format=(string)YUY2, width=(int)1400, height=(int)900, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 };
video/x-raw, format=(string)YUY2, width=(int)1280, height=(int)960, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 };
video/x-raw, format=(string)YUY2, width=(int)1360, height=(int)768, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 };
video/x-raw, format=(string)YUY2, width=(int)1280, height=(int)720, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 };
video/x-raw, format=(string)YUY2, width=(int)1024, height=(int)768, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 };
video/x-raw, format=(string)YUY2, width=(int)800, height=(int)600, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 };
video/x-raw, format=(string)YUY2, width=(int)640, height=(int)480, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 60/1, 30/1 }
        """)
        caps = pipeline.choose_video_caps(source_caps, target_caps)
        self.assertEqual(caps.to_string(), "video/x-raw, format=(string)YUY2, width=(int)1920, height=(int)1080, framerate=(fraction)30/1, pixel-aspect-ratio=(fraction)1/1, interlace-mode=(string)progressive")

        # Thinkpad X1 Carbon web cam
        source_caps = Gst.Caps.from_string("""
video/x-raw, format=(string)YUY2, width=(int)1280, height=(int)720, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction)10/1;
video/x-raw, format=(string)YUY2, width=(int)960, height=(int)540, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction)15/1;
video/x-raw, format=(string)YUY2, width=(int)848, height=(int)480, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction)20/1;
video/x-raw, format=(string)YUY2, width=(int)640, height=(int)480, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
video/x-raw, format=(string)YUY2, width=(int)640, height=(int)360, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
video/x-raw, format=(string)YUY2, width=(int)424, height=(int)240, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
video/x-raw, format=(string)YUY2, width=(int)352, height=(int)288, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
video/x-raw, format=(string)YUY2, width=(int)320, height=(int)240, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
video/x-raw, format=(string)YUY2, width=(int)320, height=(int)180, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
image/jpeg, width=(int)1280, height=(int)720, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
image/jpeg, width=(int)960, height=(int)540, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
image/jpeg, width=(int)848, height=(int)480, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
image/jpeg, width=(int)640, height=(int)480, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
image/jpeg, width=(int)640, height=(int)360, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
image/jpeg, width=(int)424, height=(int)240, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
image/jpeg, width=(int)352, height=(int)288, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
image/jpeg, width=(int)320, height=(int)240, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
image/jpeg, width=(int)320, height=(int)180, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction){ 30/1, 15/1 };
        """)
        caps = pipeline.choose_video_caps(source_caps, target_caps)
        self.assertEqual(caps.to_string(), "video/x-raw, interlace-mode=(string)progressive, format=(string)YUY2, width=(int)1280, height=(int)720, pixel-aspect-ratio=(fraction)1/1, framerate=(fraction)10/1")
