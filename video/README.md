# RationaleOps Demo Video

This Remotion project renders the 120-second, text-led hackathon walkthrough.
It uses screenshots captured from the real interactive dashboard and covers the
complete story: DataHub evidence, adaptive interview, three distinct outcomes,
deterministic validation, approval gates, and verified write-back.

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
