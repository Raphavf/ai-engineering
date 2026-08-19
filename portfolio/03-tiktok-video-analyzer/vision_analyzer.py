"""Sends each extracted frame to Claude Vision for analysis."""

import base64

import anthropic

client = anthropic.Anthropic()

ANALYSIS_PROMPT = (
    "You're a short-form video marketing analyst. Look at this frame from a "
    "TikTok video and describe: the hook type (if this looks like an "
    "opening frame), lighting quality, camera angle, and any visible "
    "selling points or on-screen text. Be concise and specific."
)


def _encode_image(frame_path: str) -> str:
    with open(frame_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def analyze_frame(frame_path: str) -> str:
    """Send one frame to Claude Vision and return the analysis text."""
    image_data = _encode_image(frame_path)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data},
                    },
                    {"type": "text", "text": ANALYSIS_PROMPT},
                ],
            }
        ],
    )
    return response.content[0].text


def analyze_frames(frame_paths: list[str]) -> list[str]:
    """Analyze a list of frames, returning one analysis string per frame."""
    return [analyze_frame(path) for path in frame_paths]
