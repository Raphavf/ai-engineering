# TikTok Video Analyzer

A pipeline that downloads a TikTok video, pulls out a handful of key frames, and uses Claude's
vision capabilities to analyze each one (hook type, lighting, camera angle, selling points), then
generates a consolidated report a marketing team can act on.

Built during prep for a role that needed fast, practical use of the Claude API and TikTok Shop
content — going from "never used the Claude API" to a working end-to-end pipeline in a few days.

## How it works

```
TikTok URL
   → yt-dlp downloads the video
   → OpenCV extracts frames at a few strategic timestamps
   → Claude Vision analyzes each frame
   → Claude consolidates the frame analyses into one report
   → report.txt
```

## Structure

- `downloader.py` — downloads the video via `yt-dlp`
- `frame_extractor.py` — pulls frames from the video with OpenCV
- `vision_analyzer.py` — sends each frame to Claude for analysis
- `report_generator.py` — asks Claude to consolidate the per-frame analyses into one report
- `main.py` — wires the pipeline together

## Running it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python main.py "https://www.tiktok.com/@creator/video/123456789"
```

If TikTok blocks the download, export a `cookies.txt` from your browser (e.g. with the "Get
cookies.txt" extension) and pass it with `--cookies cookies.txt`.

## Notes

This was built and debugged against real Windows quirks: emoji/Unicode print statements crashing in
the default `cp1252` terminal encoding, and `yt-dlp` needing to be called as a Python library rather
than a subprocess when it wasn't on PATH. Both are handled in `downloader.py`.
