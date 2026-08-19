"""Downloads a TikTok video with yt-dlp."""

import sys
import yt_dlp


def download_video(url: str, output_path: str = "video.mp4", cookies_path: str | None = None) -> str:
    """Download a TikTok video and return the local file path."""
    ydl_opts = {
        "outtmpl": output_path,
        "format": "mp4/best",
        "quiet": True,
    }
    if cookies_path:
        # Needed when TikTok blocks anonymous downloads — export cookies.txt
        # from a logged-in browser session.
        ydl_opts["cookiefile"] = cookies_path

    print(f"Downloading video: {url}", file=sys.stdout)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return output_path
