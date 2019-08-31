# Videowhisk

Videowhisk is a live video mixing server in the same vein as
[DVSwitch][1] and [Voctomix][2].  Multiple ingest nodes send audio
and/or video over the network to a mixing server that produces a mixed
version that can be saved or live streamed.

It takes strong inspiration from Voctomix, with a few differences:

1. ingest sources are created dynamically rather than configured
   statically.
2. ingest sources can send any combination of audio and video, or even
   multiple streams of the same type.
3. networking code uses Python's asyncio library.

[1]: https://web.archive.org/web/20180516022220/http://dvswitch.alioth.debian.org/wiki/
[2]: https://github.com/voc/voctomix
