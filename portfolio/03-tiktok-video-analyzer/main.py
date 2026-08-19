"""Entry point: runs the full TikTok analysis pipeline end to end."""

import argparse

from downloader import download_video
from frame_extractor import extract_frames
from vision_analyzer import analyze_frames
from report_generator import generate_report


def analyze_tiktok_video(url: str, cookies_path: str | None = None) -> str:
    video_path = download_video(url, cookies_path=cookies_path)
    frame_paths = extract_frames(video_path)
    frame_analyses = analyze_frames(frame_paths)
    report = generate_report(frame_analyses)

    with open("report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a TikTok video with Claude Vision.")
    parser.add_argument("url", help="TikTok video URL")
    parser.add_argument("--cookies", help="Path to cookies.txt, if TikTok blocks the download")
    args = parser.parse_args()

    report_text = analyze_tiktok_video(args.url, cookies_path=args.cookies)
    print("\nReport saved to report.txt\n")
    print(report_text)
