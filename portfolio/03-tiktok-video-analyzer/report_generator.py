"""Consolidates per-frame analyses into one client-ready report."""

import anthropic

client = anthropic.Anthropic()

REPORT_PROMPT_TEMPLATE = (
    "Here are frame-by-frame analyses of a TikTok video, in order:\n\n"
    "{analyses}\n\n"
    "Write a short, client-ready report summarizing the video's hook "
    "strategy, pacing, and overall strengths/weaknesses as a piece of "
    "short-form marketing content. Keep it under 200 words."
)


def generate_report(frame_analyses: list[str]) -> str:
    """Ask Claude to turn the individual frame analyses into one summary report."""
    combined = "\n\n".join(f"Frame {i + 1}: {text}" for i, text in enumerate(frame_analyses))
    prompt = REPORT_PROMPT_TEMPLATE.format(analyses=combined)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
