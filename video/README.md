# RationaleOps Demo Video

This Remotion project renders the 120-second hackathon walkthrough. It includes
a 19-second recording of the real interactive dashboard and covers the complete
story: DataHub evidence, adaptive interview, three distinct outcomes,
deterministic validation, approval gates, and verified write-back.
The embedded workflow was captured from the
[deployed dashboard](https://barebone-lab.github.io/rationaleops/) in its
deterministic **Recorded** mode so the submission remains reproducible.

## Preview and render

```bash
npm install
npm run dev
npm run render
```

The final 1920×1080, 30fps H.264 submission is written to
[`out/rationaleops-demo.mp4`](out/rationaleops-demo.mp4).

## Verify

```bash
npm run lint
npm audit
ffprobe -v error \
  -show_entries format=duration \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  out/rationaleops-demo.mp4
```

Expected duration: approximately 120 seconds, below the three-minute limit.

## Music

The background track is **“Close Up” by Michael Ramir C.**, downloaded from
[Mixkit's corporate music collection](https://mixkit.co/free-stock-music/corporate-music/).
It is used under the
[Mixkit Stock Music Free License](https://mixkit.co/license/#musicFree).
Attribution is not required by that license; the credit is retained here for
clear submission provenance. Asset-level details and checksum are recorded in
[`public/music/README.md`](public/music/README.md).
