"""Extracts a handful of frames from a video using OpenCV."""

from pathlib import Path

import cv2


def extract_frames(video_path: str, output_dir: str = "frames", num_frames: int = 5) -> list[str]:
    """Extract `num_frames` evenly-spaced frames from the video and save
    them as JPEGs. Returns the list of saved file paths.
    """
    Path(output_dir).mkdir(exist_ok=True)

    capture = cv2.VideoCapture(video_path)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

    # Evenly spaced timestamps across the video, skipping the very first
    # and last frame (usually blank or a watermark).
    positions = [int(total_frames * (i + 1) / (num_frames + 1)) for i in range(num_frames)]

    saved_paths = []
    for i, frame_position in enumerate(positions):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
        success, frame = capture.read()
        if not success:
            continue
        frame_path = f"{output_dir}/frame_{i}.jpg"
        cv2.imwrite(frame_path, frame)
        saved_paths.append(frame_path)

    capture.release()
    return saved_paths
